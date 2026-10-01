import fcntl
import hashlib
import logging
import os
import socket
import tempfile
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from threading import Lock
from typing import Any, Callable
from urllib.error import URLError
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.connectors.source_registry import SourceConfiguration, SourceRegistry, source_registry
from app.core.config import (
    AUTOMATIC_DISCOVERY_ENABLED,
    AUTOMATIC_INGESTION_ENABLED,
    AUTOMATIC_INGESTION_FAILURE_THRESHOLD,
    AUTOMATIC_INGESTION_HEALTH_COOLDOWN_SECONDS,
    AUTOMATIC_INGESTION_MAX_JOBS_PER_SOURCE,
    AUTOMATIC_INGESTION_MAX_SOURCES_PER_RUN,
    AUTOMATIC_INGESTION_TIMEOUT_SECONDS,
    DATABASE_URL,
    ATS_CATALOG_DISCOVERY_ENABLED,
    ATS_CATALOG_MANIFEST_URL,
    DISCOVERY_CATALOG_ALLOWED_HOSTS,
    DISCOVERY_CATALOG_PROVIDER,
    DISCOVERY_CATALOG_URL,
    DISCOVERY_CANDIDATES,
    SCHEDULER_ENABLED,
    SCHEDULER_HOUR,
    SCHEDULER_MINUTE,
    SCHEDULER_TIMEZONE,
)
from app.core.database import SessionLocal
from app.services.ingestion_service import IngestionService
from app.services.source_discovery_service import DiscoveryCandidate, SourceDiscoveryService
from app.services.discovery_providers import AtsCompanyCatalogProvider, DiscoveryProvider, PublicJsonCatalogProvider
from app.models.discovered_source import DiscoveredSource
from app.models.discovery_run import DiscoveryRun
from app.models.ingestion_run import IngestionRun
from app.utils.error_sanitization import sanitize_error_message

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SchedulerSettings:
    """Configuration for the daily scheduled ingestion window."""

    enabled: bool = SCHEDULER_ENABLED
    hour: int = SCHEDULER_HOUR
    minute: int = SCHEDULER_MINUTE
    timezone: str = SCHEDULER_TIMEZONE

    def __post_init__(self) -> None:
        if not 0 <= self.hour <= 23:
            raise ValueError("Scheduler hour must be between 0 and 23")
        if not 0 <= self.minute <= 59:
            raise ValueError("Scheduler minute must be between 0 and 59")
        try:
            ZoneInfo(self.timezone)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError(f"Unknown scheduler timezone: {self.timezone}") from exc

    @property
    def zone(self) -> ZoneInfo:
        return ZoneInfo(self.timezone)


class SchedulerService:
    """Runs approved ingestion sources without owning source-specific logic."""

    def __init__(
        self,
        settings: SchedulerSettings | None = None,
        registry: SourceRegistry = source_registry,
        session_factory: Callable[[], Any] = SessionLocal,
        ingestion_service_factory: Callable[..., IngestionService] = IngestionService,
        discovery_service_factory: Callable[..., SourceDiscoveryService] = SourceDiscoveryService,
        discovery_candidates: list[dict[str, str]] | None = None,
        discovery_providers: list[DiscoveryProvider] | None = None,
        automatic_ingestion_enabled: bool = AUTOMATIC_INGESTION_ENABLED,
        max_automatic_sources: int = AUTOMATIC_INGESTION_MAX_SOURCES_PER_RUN,
        max_automatic_jobs: int = AUTOMATIC_INGESTION_MAX_JOBS_PER_SOURCE,
        automatic_timeout_seconds: int = AUTOMATIC_INGESTION_TIMEOUT_SECONDS,
        automatic_failure_threshold: int = AUTOMATIC_INGESTION_FAILURE_THRESHOLD,
        automatic_health_cooldown_seconds: int = AUTOMATIC_INGESTION_HEALTH_COOLDOWN_SECONDS,
        clock: Callable[[], datetime] | None = None,
        automatic_run_lock_path: str | None = None,
    ) -> None:
        self.settings = settings or SchedulerSettings()
        self.registry = registry
        self.session_factory = session_factory
        self.ingestion_service_factory = ingestion_service_factory
        self.discovery_service_factory = discovery_service_factory
        self.discovery_candidates = discovery_candidates if discovery_candidates is not None else DISCOVERY_CANDIDATES
        self.discovery_providers = discovery_providers if discovery_providers is not None else self._configured_providers()
        self.automatic_ingestion_enabled = automatic_ingestion_enabled
        self.max_automatic_sources = max(0, max_automatic_sources)
        self.max_automatic_jobs = max(0, max_automatic_jobs)
        self.automatic_timeout_seconds = max(1, automatic_timeout_seconds)
        self.automatic_failure_threshold = max(1, automatic_failure_threshold)
        self.automatic_health_cooldown_seconds = max(0, automatic_health_cooldown_seconds)
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        database_key = hashlib.sha256(DATABASE_URL.encode("utf-8")).hexdigest()[:16]
        self.automatic_run_lock_path = automatic_run_lock_path or os.path.join(
            tempfile.gettempdir(),
            f"contract-hunter-automatic-ingestion-{database_key}.lock",
        )
        self._source_locks: dict[tuple[str, str], Lock] = {}
        self._locks_guard = Lock()
        self._last_due_date: date | None = None

    def next_run_at(self, after: datetime) -> datetime:
        """Return the next timezone-aware scheduled instant after ``after``."""
        if after.tzinfo is None:
            raise ValueError("Scheduler datetimes must be timezone-aware")
        local_after = after.astimezone(self.settings.zone)
        scheduled = local_after.replace(
            hour=self.settings.hour,
            minute=self.settings.minute,
            second=0,
            microsecond=0,
        )
        if scheduled <= local_after:
            scheduled += timedelta(days=1)
        return scheduled

    def run_if_due(self, now: datetime) -> dict[str, Any]:
        """Run one daily cycle when ``now`` is at or after today's schedule."""
        if now.tzinfo is None:
            raise ValueError("Scheduler datetimes must be timezone-aware")
        if not self.settings.enabled:
            return self._disabled_result()

        local_now = now.astimezone(self.settings.zone)
        scheduled = local_now.replace(
            hour=self.settings.hour,
            minute=self.settings.minute,
            second=0,
            microsecond=0,
        )
        if local_now < scheduled or self._last_due_date == local_now.date():
            return {"status": "not_due", "results": []}
        self._last_due_date = local_now.date()
        return self.run_cycle()

    def trigger_manual(self) -> dict[str, Any]:
        """Run the same approved-source cycle immediately for internal callers/tests."""
        return self.run_cycle()

    def run_cycle(self) -> dict[str, Any]:
        """Run all enabled configurations, isolating source failures."""
        if not self.settings.enabled:
            return self._disabled_result()

        logger.info("scheduler_cycle_started")
        discovery_result = self._run_discovery()
        results: list[dict[str, Any]] = []
        configured_sources = self.registry.enabled_configurations(include_discovered=False)
        for configuration in configured_sources:
            result = self._run_source(configuration)
            results.append(result)
        automatic_result = self._run_automatic_ingestion(configured_sources, discovery_result)
        logger.info("scheduler_cycle_completed", extra={"source_count": len(results)})
        response = {"status": "completed", "results": results}
        if discovery_result is not None:
            response["discovery"] = discovery_result
        response["automatic_ingestion"] = automatic_result
        return response

    def _run_automatic_ingestion(
        self,
        configured_sources: list[SourceConfiguration],
        discovery_result: dict[str, Any] | None,
    ) -> dict[str, Any]:
        if not self.automatic_ingestion_enabled or self.max_automatic_sources == 0:
            return self._automatic_run_result("disabled")

        lock_fd = self._acquire_automatic_run_lock()
        if lock_fd is None:
            logger.info("scheduler_automatic_run_skipped_overlap")
            return self._automatic_run_result("skipped_overlap")

        run_id = None
        health_events: list[dict[str, Any]] = []
        results: list[dict[str, Any]] = []
        automatic_sources: list[SourceConfiguration] = []
        attempted_keys: set[tuple[str, str]] = set()
        try:
            now = self._now_utc()
            health_events.extend(self._recover_stale_automatic_runs(now))
            run_id = self._start_automatic_run(now)
            automatic_sources, recovery_keys, selection_events, failures_before = self._select_automatic_sources(
                configured_sources
            )
            health_events.extend(selection_events)
            unique_sources: list[SourceConfiguration] = []
            selected_keys: set[tuple[str, str]] = set()
            for configuration in automatic_sources:
                key = (configuration.source.lower(), configuration.identifier)
                if key in selected_keys:
                    health_events.append(self._source_health_event(
                        configuration,
                        "skipped_duplicate_selection",
                        self._now_utc(),
                    ))
                    continue
                selected_keys.add(key)
                unique_sources.append(configuration)
            automatic_sources = unique_sources
            self._persist_automatic_run_progress(run_id, automatic_sources, results, health_events)

            for configuration in automatic_sources:
                key = (configuration.source.lower(), configuration.identifier)
                if key in attempted_keys:
                    health_events.append(self._source_health_event(
                        configuration,
                        "skipped_duplicate_attempt",
                        self._now_utc(),
                    ))
                    self._persist_automatic_run_progress(run_id, automatic_sources, results, health_events)
                    continue

                attempted_keys.add(key)
                health_events.append(self._source_health_event(
                    configuration,
                    "recovery_attempted" if key in recovery_keys else "source_attempted",
                    self._now_utc(),
                ))
                self._persist_automatic_run_progress(run_id, automatic_sources, results, health_events)
                result = self._run_source(configuration, automatic=True)
                results.append(result)
                status = result.get("status")
                failure_kind = "timeout" if result.get("is_timeout") else "source_failure"
                if status == "skipped_overlap":
                    event = "recovery_skipped_overlap" if key in recovery_keys else "source_skipped_overlap"
                elif status == "completed":
                    event = "recovered" if key in recovery_keys else "ingestion_succeeded"
                elif key in recovery_keys:
                    event = "recovery_failed_cooldown_restarted"
                elif status == "failed" and failures_before.get(key, 0) + 1 >= self.automatic_failure_threshold:
                    event = "failed_entered_cooldown"
                elif result.get("is_timeout"):
                    event = "source_timeout"
                else:
                    event = "source_failed"
                outcome_event = self._source_health_event(
                    configuration,
                    event,
                    self._now_utc(),
                    failure_kind=failure_kind if status == "failed" else None,
                )
                health_events.append(outcome_event)
                self._persist_automatic_run_progress(run_id, automatic_sources, results, health_events)

            completed_at = self._now_utc()
            attempted_count = sum(result.get("status") != "skipped_overlap" for result in results)
            succeeded_count = sum(result.get("status") == "completed" for result in results)
            failed_count = sum(result.get("status") == "failed" for result in results)
            skipped_events = {"skipped_cooldown_active", "skipped_duplicate_selection", "skipped_duplicate_attempt"}
            skipped_cooldown = sum(event.get("event") == "skipped_cooldown_active" for event in health_events)
            skipped_count = sum(event.get("event") in skipped_events for event in health_events) + sum(
                result.get("status", "").startswith("skipped") for result in results
            )
            health_events.append({
                "event": "run_completed",
                "timestamp": completed_at.isoformat(),
                "attempted_count": attempted_count,
                "skipped_count": skipped_count,
                "skipped_cooldown_count": skipped_cooldown,
            })
            self._record_automatic_counts(
                run_id,
                automatic_sources,
                results,
                health_events,
                status="completed",
            )
            for event in health_events:
                if "source" in event:
                    logger.info("scheduler_automatic_source_health", extra=event)
            return {
                "status": "completed",
                "run_id": run_id,
                "selected": len(automatic_sources),
                "attempted": attempted_count,
                "succeeded": succeeded_count,
                "failed": failed_count,
                "skipped": skipped_count,
                "skipped_cooldown": skipped_cooldown,
                "results": results,
                "health_events": health_events,
            }
        except Exception as exc:
            safe_error = sanitize_error_message(exc)
            if run_id is not None:
                self._finish_automatic_run_failed(
                    run_id,
                    safe_error,
                    automatic_sources,
                    results,
                    health_events,
                    attempted_count=sum(result.get("status") != "skipped_overlap" for result in results),
                    skipped_count=sum(event.get("event", "").startswith("skipped_") for event in health_events)
                    + sum(result.get("status", "").startswith("skipped") for result in results),
                )
            logger.error("scheduler_automatic_run_failed", extra={"error": safe_error})
            return {
                "status": "failed",
                "run_id": run_id,
                "selected": len(automatic_sources),
                "attempted": sum(result.get("status") != "skipped_overlap" for result in results),
                "succeeded": sum(result.get("status") == "completed" for result in results),
                "failed": sum(result.get("status") == "failed" for result in results),
                "skipped": sum(event.get("event", "").startswith("skipped_") for event in health_events)
                + sum(result.get("status", "").startswith("skipped") for result in results),
                "skipped_cooldown": sum(event.get("event") == "skipped_cooldown_active" for event in health_events),
                "results": results,
                "health_events": health_events,
                "message": safe_error,
            }
        finally:
            self._release_automatic_run_lock(lock_fd)

    @staticmethod
    def _automatic_run_result(status: str) -> dict[str, Any]:
        return {
            "status": status,
            "run_id": None,
            "selected": 0,
            "attempted": 0,
            "succeeded": 0,
            "failed": 0,
            "skipped": 0,
            "skipped_cooldown": 0,
            "results": [],
            "health_events": [],
        }

    def _acquire_automatic_run_lock(self) -> int | None:
        try:
            lock_fd = os.open(self.automatic_run_lock_path, os.O_CREAT | os.O_RDWR, 0o600)
        except OSError:
            logger.exception("scheduler_automatic_run_lock_open_failed")
            return None
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return lock_fd
        except BlockingIOError:
            os.close(lock_fd)
            return None
        except OSError:
            os.close(lock_fd)
            logger.exception("scheduler_automatic_run_lock_failed")
            return None

    @staticmethod
    def _release_automatic_run_lock(lock_fd: int) -> None:
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)
        finally:
            os.close(lock_fd)

    def _start_automatic_run(self, started_at: datetime) -> int:
        session = self.session_factory()
        try:
            run = DiscoveryRun(
                run_type="automatic_ingestion",
                started_at=started_at.replace(tzinfo=None),
                status="running",
                automatic_ingestion_health_results=[{
                    "event": "run_started",
                    "timestamp": started_at.isoformat(),
                }],
            )
            session.add(run)
            session.commit()
            session.refresh(run)
            return run.id
        finally:
            session.close()

    def _recover_stale_automatic_runs(self, now: datetime) -> list[dict[str, Any]]:
        session = self.session_factory()
        events: list[dict[str, Any]] = []
        safe_error = sanitize_error_message(RuntimeError("Automatic ingestion interrupted by process restart"))
        database_now = now.replace(tzinfo=None)
        stale_before = database_now - timedelta(
            seconds=max(1, self.max_automatic_sources) * self.automatic_timeout_seconds + 60
        )
        try:
            stale_runs = session.query(DiscoveryRun).filter(
                DiscoveryRun.run_type == "automatic_ingestion",
                DiscoveryRun.status == "running",
                DiscoveryRun.started_at <= stale_before,
            ).all()
            for stale_run in stale_runs:
                event = {
                    "event": "run_interrupted",
                    "timestamp": now.isoformat(),
                    "run_id": stale_run.id,
                }
                stale_run.status = "failed"
                stale_run.completed_at = database_now
                stale_run.message = safe_error
                stale_run.automatic_ingestion_health_results = [
                    *(stale_run.automatic_ingestion_health_results or []), event
                ]
                events.append(event)

            stale_ingestion_runs = session.query(IngestionRun).filter(
                IngestionRun.is_automatic.is_(True),
                IngestionRun.status == "running",
                IngestionRun.started_at <= stale_before,
            ).all()
            for stale_run in stale_ingestion_runs:
                stale_run.status = "failed"
                stale_run.completed_at = database_now
                stale_run.message = safe_error
                record = session.query(DiscoveredSource).filter_by(
                    source=stale_run.source.lower(),
                    identifier=stale_run.source_identifier,
                ).first()
                if record is None:
                    continue
                record.last_automatic_ingestion_attempt_at = database_now
                record.consecutive_automatic_ingestion_failures += 1
                record.last_automatic_ingestion_error = safe_error
                unhealthy = record.consecutive_automatic_ingestion_failures >= self.automatic_failure_threshold
                if unhealthy:
                    record.automatic_ingestion_cooldown_started_at = now
                events.append({
                    "source": record.source,
                    "source_identifier": record.identifier,
                    "event": "source_run_interrupted",
                    "health_state": "unhealthy" if unhealthy else "degraded",
                    "timestamp": now.isoformat(),
                })
            if stale_runs or stale_ingestion_runs:
                session.commit()
            return events
        except Exception:
            session.rollback()
            logger.exception("scheduler_stale_run_recovery_failed")
            return events
        finally:
            session.close()

    def _persist_automatic_run_progress(
        self,
        run_id: int,
        selected_sources: list[SourceConfiguration],
        results: list[dict[str, Any]],
        health_events: list[dict[str, Any]],
    ) -> None:
        session = self.session_factory()
        try:
            run = session.get(DiscoveryRun, run_id)
            if run is None:
                return
            run.selected_count = len(selected_sources)
            run.succeeded_count = sum(result.get("status") == "completed" for result in results)
            run.failed_count = sum(result.get("status") == "failed" for result in results)
            started_event = next(
                (event for event in run.automatic_ingestion_health_results or [] if event.get("event") == "run_started"),
                None,
            )
            run.automatic_ingestion_health_results = ([started_event] if started_event else []) + health_events
            session.commit()
        finally:
            session.close()

    def _finish_automatic_run_failed(
        self,
        run_id: int,
        error: str,
        selected_sources: list[SourceConfiguration],
        results: list[dict[str, Any]],
        health_events: list[dict[str, Any]],
        attempted_count: int,
        skipped_count: int,
    ) -> None:
        self._record_automatic_counts(
            run_id,
            selected_sources,
            results,
            health_events + [{
                "event": "run_failed",
                "timestamp": self._now_utc().isoformat(),
                "attempted_count": attempted_count,
                "skipped_count": skipped_count,
            }],
            status="failed",
            message=error,
        )

    def _select_automatic_sources(
        self,
        configured_sources: list[SourceConfiguration],
    ) -> tuple[list[SourceConfiguration], set[tuple[str, str]], list[dict[str, Any]], dict[tuple[str, str], int]]:
        if not self.automatic_ingestion_enabled or self.max_automatic_sources == 0:
            return [], set(), [], {}
        configured_keys = {(item.source.lower(), item.identifier) for item in configured_sources}
        now = self._now_utc()
        session = self.session_factory()
        try:
            records = session.query(DiscoveredSource).filter(
                DiscoveredSource.eligible.is_(True),
                DiscoveredSource.validation_status == "valid",
                DiscoveredSource.status == "validated",
                DiscoveredSource.source.in_(("ashby", "greenhouse", "lever")),
            ).order_by(
                DiscoveredSource.last_validated_at.desc(),
                DiscoveredSource.source.asc(),
                DiscoveredSource.identifier.asc(),
            ).all()
            selected: list[SourceConfiguration] = []
            recovery_keys: set[tuple[str, str]] = set()
            health_events: list[dict[str, Any]] = []
            failures_before: dict[tuple[str, str], int] = {}
            seen: set[tuple[str, str]] = set()
            cooldown_changed = False
            for record in records:
                key = (record.source.lower(), record.identifier)
                if key in configured_keys or key in seen:
                    continue
                failure_count = record.consecutive_automatic_ingestion_failures
                recovery = failure_count >= self.automatic_failure_threshold
                cooldown_started_at = self._as_utc(record.automatic_ingestion_cooldown_started_at)
                if recovery:
                    if cooldown_started_at is None:
                        cooldown_started_at = now
                        record.automatic_ingestion_cooldown_started_at = now
                        cooldown_changed = True
                    cooldown_until = cooldown_started_at + timedelta(
                        seconds=self.automatic_health_cooldown_seconds
                    )
                    if now < cooldown_until:
                        health_events.append(self._source_health_event(
                            record,
                            "skipped_cooldown_active",
                            now,
                            cooldown_until=cooldown_until,
                        ))
                        continue
                configuration = self.registry.resolve(record.source, record.identifier)
                if configuration is None:
                    continue
                if len(selected) >= self.max_automatic_sources:
                    continue
                seen.add(key)
                selected.append(configuration)
                failures_before[key] = failure_count
                if recovery:
                    recovery_keys.add(key)
                    health_events.append(self._source_health_event(
                        record,
                        "selected_recovery",
                        now,
                        cooldown_until=cooldown_until,
                    ))
                else:
                    health_events.append(self._source_health_event(record, "selected", now))
            if cooldown_changed:
                session.commit()
            return selected, recovery_keys, health_events, failures_before
        finally:
            session.close()

    def _now_utc(self) -> datetime:
        now = self.clock()
        if now.tzinfo is None:
            raise ValueError("Scheduler clock must return a timezone-aware datetime")
        return now.astimezone(timezone.utc)

    @staticmethod
    def _as_utc(value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    @staticmethod
    def _source_health_event(
        source: SourceConfiguration | DiscoveredSource,
        event: str,
        timestamp: datetime,
        cooldown_until: datetime | None = None,
        failure_kind: str | None = None,
    ) -> dict[str, Any]:
        result = {
            "source": source.source,
            "source_identifier": source.identifier,
            "event": event,
            "timestamp": timestamp.isoformat(),
            "health_state": (
                "unhealthy" if event in {
                    "skipped_cooldown_active",
                    "selected_recovery",
                    "recovery_skipped_overlap",
                    "recovery_failed_cooldown_restarted",
                    "failed_entered_cooldown",
                } else "degraded" if failure_kind is not None or event in {"ingestion_failed", "source_failed", "source_timeout"}
                else "healthy"
            ),
        }
        if failure_kind is not None:
            result["failure_kind"] = failure_kind
        if cooldown_until is not None:
            result["cooldown_until"] = cooldown_until.isoformat()
        return result
    def _run_discovery(self) -> dict[str, Any] | None:
        if not self.discovery_candidates and not self.discovery_providers:
            return None
        session = None
        try:
            session = self.session_factory()
            candidates = [DiscoveryCandidate(**candidate) for candidate in self.discovery_candidates]
            service = self.discovery_service_factory(session, registry=self.registry)
            if self.discovery_providers:
                result = service.discover_from_providers(self.discovery_providers, candidates)
            else:
                result = service.discover(candidates)
            logger.info("scheduler_discovery_completed", extra={"validated_count": result.get("validated", 0)})
            return result
        except Exception as exc:
            logger.exception("scheduler_discovery_failed")
            return {"status": "failed", "message": str(exc)}
        finally:
            if session is not None:
                session.close()

    @staticmethod
    def _configured_providers() -> list[DiscoveryProvider]:
        providers: list[DiscoveryProvider] = []
        if ATS_CATALOG_DISCOVERY_ENABLED:
            try:
                providers.append(AtsCompanyCatalogProvider(manifest_url=ATS_CATALOG_MANIFEST_URL))
            except ValueError:
                logger.exception("ats_catalog_provider_configuration_invalid")
        if not AUTOMATIC_DISCOVERY_ENABLED or not DISCOVERY_CATALOG_URL:
            return providers
        try:
            providers.append(PublicJsonCatalogProvider(
                catalog_url=DISCOVERY_CATALOG_URL,
                name=DISCOVERY_CATALOG_PROVIDER,
                allowed_catalog_hosts=DISCOVERY_CATALOG_ALLOWED_HOSTS,
            ))
        except ValueError:
            logger.exception("discovery_provider_configuration_invalid")
        return providers

    def _run_source(self, configuration: SourceConfiguration, automatic: bool = False) -> dict[str, Any]:
        key = (configuration.source.lower(), configuration.identifier)
        with self._locks_guard:
            source_lock = self._source_locks.setdefault(key, Lock())
        if not source_lock.acquire(blocking=False):
            logger.warning(
                "scheduler_source_skipped_overlap",
                extra={"source": configuration.source, "source_identifier": configuration.identifier},
            )
            return {
                "source": configuration.source,
                "source_identifier": configuration.identifier,
                "status": "skipped_overlap",
            }

        session = None
        try:
            session = self.session_factory()
            logger.info(
                "scheduler_source_started",
                extra={"source": configuration.source, "source_identifier": configuration.identifier},
            )
            ingestion_service = self.ingestion_service_factory(session, registry=self.registry)
            if automatic:
                result = ingestion_service.ingest(
                    configuration.source,
                    configuration.identifier,
                    max_jobs=self.max_automatic_jobs,
                    timeout_seconds=self.automatic_timeout_seconds,
                    automatic=True,
                )
            else:
                result = ingestion_service.ingest(configuration.source, configuration.identifier)
            if automatic:
                succeeded = result.get("status") == "completed"
                error = None if succeeded else RuntimeError(
                    f"Automatic ingestion returned status: {result.get('status', 'unknown')}"
                )
                self._record_automatic_health(configuration, succeeded=succeeded, error=error)
            logger.info(
                "scheduler_source_completed",
                extra={"source": configuration.source, "source_identifier": configuration.identifier},
            )
            return result
        except Exception as exc:
            if automatic:
                self._record_automatic_health(configuration, succeeded=False, error=exc)
            safe_message = sanitize_error_message(exc)
            is_timeout = self._is_timeout_error(exc)
            logger.error(
                "scheduler_source_failed",
                extra={
                    "source": configuration.source,
                    "source_identifier": configuration.identifier,
                    "error": safe_message,
                    "is_timeout": is_timeout,
                },
            )
            return {
                "source": configuration.source,
                "source_identifier": configuration.identifier,
                "status": "failed",
                "message": safe_message if automatic else str(exc),
                "is_timeout": is_timeout,
            }
        finally:
            if session is not None:
                session.close()
            source_lock.release()

    @staticmethod
    def _is_timeout_error(error: Exception) -> bool:
        if isinstance(error, (TimeoutError, socket.timeout)):
            return True
        return isinstance(error, URLError) and isinstance(error.reason, (TimeoutError, socket.timeout))

    def _record_automatic_health(
        self,
        configuration: SourceConfiguration,
        succeeded: bool,
        error: Exception | None = None,
    ) -> None:
        session = None
        try:
            session = self.session_factory()
            record = session.query(DiscoveredSource).filter_by(
                source=configuration.source.lower(),
                identifier=configuration.identifier,
            ).first()
            if record is None:
                return
            now = self._now_utc()
            database_now = now.replace(tzinfo=None)
            record.last_automatic_ingestion_attempt_at = database_now
            if succeeded:
                record.last_automatic_ingestion_success_at = database_now
                record.consecutive_automatic_ingestion_failures = 0
                record.last_automatic_ingestion_error = None
                record.automatic_ingestion_cooldown_started_at = None
            else:
                record.consecutive_automatic_ingestion_failures += 1
                record.last_automatic_ingestion_error = sanitize_error_message(error)
                if record.consecutive_automatic_ingestion_failures >= self.automatic_failure_threshold:
                    record.automatic_ingestion_cooldown_started_at = now
            session.commit()
        except Exception:
            if session is not None:
                session.rollback()
            logger.exception(
                "scheduler_automatic_health_update_failed",
                extra={"source": configuration.source, "source_identifier": configuration.identifier},
            )
        finally:
            if session is not None:
                session.close()

    def _record_automatic_counts(
        self,
        run_id: int,
        selected_sources: list[SourceConfiguration],
        results: list[dict[str, Any]],
        health_events: list[dict[str, Any]],
        status: str,
        message: str | None = None,
    ) -> None:
        session = self.session_factory()
        try:
            run = session.get(DiscoveryRun, run_id)
            if run is None:
                return
            now = self._now_utc().replace(tzinfo=None)
            run.selected_count = len(selected_sources)
            run.succeeded_count = sum(result.get("status") == "completed" for result in results)
            run.failed_count = sum(result.get("status") == "failed" for result in results)
            run.completed_at = now
            run.status = status
            run.message = message
            started_event = next(
                (event for event in run.automatic_ingestion_health_results or [] if event.get("event") == "run_started"),
                None,
            )
            run.automatic_ingestion_health_results = ([started_event] if started_event else []) + health_events
            session.commit()
        finally:
            session.close()
    @staticmethod
    def _disabled_result() -> dict[str, Any]:
        logger.info("scheduler_disabled")
        return {"status": "disabled", "results": []}