from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from sqlalchemy import and_, case, func
from sqlalchemy.orm import Session

from app.core.config import AUTOMATIC_INGESTION_FAILURE_THRESHOLD, AUTOMATIC_INGESTION_HEALTH_COOLDOWN_SECONDS
from app.models.discovered_source import DiscoveredSource
from app.models.discovery_run import DiscoveryRun
from app.models.ingestion_run import IngestionRun
from app.utils.error_sanitization import sanitize_error_message

SUPPORTED_SOURCES = ("ashby", "greenhouse", "lever")
RECENT_FAILURE_WINDOW = timedelta(days=7)
RECENT_RUN_LIMIT = 20
RECENT_SOURCE_EVENT_LIMIT = 5
_EVENT_FIELDS = ("source", "source_identifier", "event", "health_state", "timestamp", "cooldown_until")


class SourceHealthService:
    """Build a read-only operational view from discovered-source and ingestion audit data."""

    def __init__(
        self,
        db: Session,
        failure_threshold: int = AUTOMATIC_INGESTION_FAILURE_THRESHOLD,
        cooldown_seconds: int = AUTOMATIC_INGESTION_HEALTH_COOLDOWN_SECONDS,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.db = db
        self.failure_threshold = max(1, failure_threshold)
        self.cooldown_seconds = max(0, cooldown_seconds)
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    def summarize(self) -> dict[str, Any]:
        now = self._now_utc()
        cutoff = (now - RECENT_FAILURE_WINDOW).replace(tzinfo=None)
        records = self.db.query(DiscoveredSource).order_by(
            DiscoveredSource.source.asc(),
            DiscoveredSource.identifier.asc(),
        ).all()
        ingestion_stats = self._ingestion_stats(cutoff)
        activity_by_source, recent_runs = self._recent_health_activity()

        sources = [
            self._source_summary(record, ingestion_stats, activity_by_source, now)
            for record in records
        ]
        active_sources = [source for source in sources if source["automatic_ingestion_eligible"]]
        healthy_sources = [source for source in active_sources if source["health_state"] == "healthy"]
        unhealthy_sources = [source for source in active_sources if source["health_state"] != "healthy"]
        cooldown_sources = [source for source in unhealthy_sources if source["in_cooldown"]]
        recovery_sources = [source for source in unhealthy_sources if source["eligible_for_recovery"]]
        latest_successes = [source["most_recent_successful_ingestion"] for source in sources]
        latest_failures = [source["most_recent_failure"] for source in sources]

        return {
            "generated_at": self._iso(now),
            "failure_threshold": self.failure_threshold,
            "health_cooldown_seconds": self.cooldown_seconds,
            "recent_failure_window_seconds": int(RECENT_FAILURE_WINDOW.total_seconds()),
            "summary": {
                "total_discovered_sources": len(records),
                "healthy_sources": len(healthy_sources),
                "unhealthy_sources": len(unhealthy_sources),
                "sources_in_cooldown": len(cooldown_sources),
                "sources_eligible_for_recovery": len(recovery_sources),
                "sources_never_successfully_ingested": sum(
                    source["never_successfully_ingested"] for source in sources
                ),
                "total_ingestion_failures": sum(source["total_failures"] for source in sources),
                "recent_ingestion_failures": sum(source["recent_failures"] for source in sources),
                "current_consecutive_failure_count": sum(
                    source["consecutive_failures"] for source in sources
                ),
                "most_recent_successful_ingestion": max(
                    (value for value in latest_successes if value is not None),
                    default=None,
                ),
                "most_recent_failure": max(
                    (value for value in latest_failures if value is not None),
                    default=None,
                ),
            },
            "sources": sources,
            "recent_runs": recent_runs,
        }

    def _ingestion_stats(self, cutoff: datetime) -> dict[tuple[str, str], dict[str, Any]]:
        failed = IngestionRun.status == "failed"
        completed = IngestionRun.status == "completed"
        finished_at = func.coalesce(IngestionRun.completed_at, IngestionRun.started_at)
        rows = self.db.query(
            IngestionRun.source,
            IngestionRun.source_identifier,
            func.max(case((completed, finished_at), else_=None)).label("last_success"),
            func.max(case((failed, finished_at), else_=None)).label("last_failure"),
            func.coalesce(func.sum(case((failed, 1), else_=0)), 0).label("total_failures"),
            func.coalesce(func.sum(case((and_(failed, finished_at >= cutoff), 1), else_=0)), 0).label(
                "recent_failures"
            ),
        ).filter(IngestionRun.source.in_(SUPPORTED_SOURCES)).group_by(
            IngestionRun.source,
            IngestionRun.source_identifier,
        ).all()
        return {
            (source, identifier): {
                "last_success": last_success,
                "last_failure": last_failure,
                "total_failures": int(total_failures or 0),
                "recent_failures": int(recent_failures or 0),
            }
            for source, identifier, last_success, last_failure, total_failures, recent_failures in rows
        }

    def _recent_health_activity(
        self,
    ) -> tuple[dict[tuple[str, str], list[dict[str, Any]]], list[dict[str, Any]]]:
        runs = self.db.query(DiscoveryRun).filter(
            DiscoveryRun.automatic_ingestion_health_results.is_not(None)
        ).order_by(
            DiscoveryRun.started_at.desc(),
            DiscoveryRun.id.desc(),
        ).limit(RECENT_RUN_LIMIT).all()
        activity_by_source: dict[tuple[str, str], list[dict[str, Any]]] = {}
        recent_runs: list[dict[str, Any]] = []
        for run in runs:
            safe_events = []
            for event in (run.automatic_ingestion_health_results or []):
                if not isinstance(event, dict):
                    continue
                safe_event = {field: event[field] for field in _EVENT_FIELDS if field in event}
                source = safe_event.get("source")
                identifier = safe_event.get("source_identifier")
                if not isinstance(source, str) or not isinstance(identifier, str):
                    continue
                safe_events.append(safe_event)
                key = (source.lower(), identifier)
                source_events = activity_by_source.setdefault(key, [])
                if len(source_events) < RECENT_SOURCE_EVENT_LIMIT:
                    source_events.append(safe_event)
            recent_runs.append({
                "run_id": run.id,
                "run_type": run.run_type,
                "started_at": self._iso(run.started_at),
                "completed_at": self._iso(run.completed_at),
                "status": run.status,
                "selected_count": run.selected_count,
                "succeeded_count": run.succeeded_count,
                "failed_count": run.failed_count,
                "health_events": safe_events,
            })
        return activity_by_source, recent_runs

    def _source_summary(
        self,
        record: DiscoveredSource,
        ingestion_stats: dict[tuple[str, str], dict[str, Any]],
        activity_by_source: dict[tuple[str, str], list[dict[str, Any]]],
        now: datetime,
    ) -> dict[str, Any]:
        key = (record.source.lower(), record.identifier)
        stats = ingestion_stats.get(key, {})
        consecutive_failures = record.consecutive_automatic_ingestion_failures
        automatic_eligible = (
            record.source.lower() in SUPPORTED_SOURCES
            and record.eligible
            and record.status == "validated"
            and record.validation_status == "valid"
        )
        unhealthy = automatic_eligible and consecutive_failures >= self.failure_threshold
        cooldown_started_at = self._as_utc(record.automatic_ingestion_cooldown_started_at)
        cooldown_until = (
            cooldown_started_at + timedelta(seconds=self.cooldown_seconds)
            if cooldown_started_at is not None
            else None
        )
        in_cooldown = unhealthy and (cooldown_until is None or now < cooldown_until)
        eligible_for_recovery = unhealthy and cooldown_until is not None and now >= cooldown_until
        automatic_success = self._as_utc(record.last_automatic_ingestion_success_at)
        last_success = self._as_utc(stats.get("last_success")) or automatic_success
        last_failure = self._as_utc(stats.get("last_failure"))
        error = record.last_automatic_ingestion_error
        safe_error = sanitize_error_message(RuntimeError(error)) if error else None

        if not automatic_eligible:
            health_state = "inactive"
        elif in_cooldown:
            health_state = "cooldown"
        elif eligible_for_recovery:
            health_state = "recovery_eligible"
        else:
            health_state = "healthy"

        return {
            "source": record.source,
            "identifier": record.identifier,
            "company_name": record.company_name,
            "status": record.status,
            "validation_status": record.validation_status,
            "automatic_ingestion_eligible": automatic_eligible,
            "health_state": health_state,
            "consecutive_failures": consecutive_failures,
            "last_automatic_ingestion_attempt_at": self._iso(
                self._as_utc(record.last_automatic_ingestion_attempt_at)
            ),
            "last_automatic_ingestion_success_at": self._iso(automatic_success),
            "most_recent_successful_ingestion": self._iso(last_success),
            "most_recent_failure": self._iso(last_failure),
            "last_error": safe_error,
            "total_failures": stats.get("total_failures", 0),
            "recent_failures": stats.get("recent_failures", 0),
            "never_successfully_ingested": last_success is None,
            "in_cooldown": in_cooldown,
            "cooldown_started_at": self._iso(cooldown_started_at),
            "cooldown_until": self._iso(cooldown_until),
            "eligible_for_recovery": eligible_for_recovery,
            "recent_health_events": activity_by_source.get(key, []),
        }

    def _now_utc(self) -> datetime:
        now = self.clock()
        if now.tzinfo is None:
            raise ValueError("Source health clock must return a timezone-aware datetime")
        return now.astimezone(timezone.utc)

    @staticmethod
    def _as_utc(value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    @classmethod
    def _iso(cls, value: datetime | None) -> str | None:
        normalized = cls._as_utc(value)
        return normalized.isoformat() if normalized is not None else None