import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from threading import Lock
from typing import Any, Callable
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.connectors.source_registry import SourceConfiguration, SourceRegistry, source_registry
from app.core.config import (
    AUTOMATIC_DISCOVERY_ENABLED,
    AUTOMATIC_INGESTION_ENABLED,
    AUTOMATIC_INGESTION_MAX_JOBS_PER_SOURCE,
    AUTOMATIC_INGESTION_MAX_SOURCES_PER_RUN,
    AUTOMATIC_INGESTION_TIMEOUT_SECONDS,
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
        automatic_sources = self._select_automatic_sources(configured_sources)
        automatic_results = [self._run_source(configuration, automatic=True) for configuration in automatic_sources]
        self._record_automatic_counts(discovery_result, automatic_results)
        logger.info("scheduler_cycle_completed", extra={"source_count": len(results)})
        response = {"status": "completed", "results": results}
        if discovery_result is not None:
            response["discovery"] = discovery_result
        response["automatic_ingestion"] = {
            "selected": len(automatic_sources),
            "succeeded": sum(result.get("status") == "completed" for result in automatic_results),
            "failed": sum(result.get("status") == "failed" for result in automatic_results),
            "results": automatic_results,
        }
        return response

    def _select_automatic_sources(self, configured_sources: list[SourceConfiguration]) -> list[SourceConfiguration]:
        if not self.automatic_ingestion_enabled or self.max_automatic_sources == 0:
            return []
        configured_keys = {(item.source.lower(), item.identifier) for item in configured_sources}
        session = self.session_factory()
        try:
            records = session.query(DiscoveredSource).filter(
                DiscoveredSource.eligible.is_(True),
                DiscoveredSource.validation_status == "valid",
                DiscoveredSource.status == "validated",
            ).order_by(DiscoveredSource.last_validated_at.desc()).limit(self.max_automatic_sources * 2).all()
            selected: list[SourceConfiguration] = []
            seen: set[tuple[str, str]] = set()
            for record in records:
                key = (record.source.lower(), record.identifier)
                if key in configured_keys or key in seen:
                    continue
                configuration = self.registry.resolve(record.source, record.identifier)
                if configuration is None:
                    continue
                seen.add(key)
                selected.append(configuration)
                if len(selected) >= self.max_automatic_sources:
                    break
            return selected
        finally:
            session.close()
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
                )
            else:
                result = ingestion_service.ingest(configuration.source, configuration.identifier)
            logger.info(
                "scheduler_source_completed",
                extra={"source": configuration.source, "source_identifier": configuration.identifier},
            )
            return result
        except Exception as exc:
            logger.exception(
                "scheduler_source_failed",
                extra={"source": configuration.source, "source_identifier": configuration.identifier},
            )
            return {
                "source": configuration.source,
                "source_identifier": configuration.identifier,
                "status": "failed",
                "message": str(exc),
            }
        finally:
            if session is not None:
                session.close()
            source_lock.release()

    def _record_automatic_counts(self, discovery_result: dict[str, Any] | None, results: list[dict[str, Any]]) -> None:
        run_id = discovery_result.get("run_id") if discovery_result else None
        if run_id is None:
            return
        session = self.session_factory()
        try:
            run = session.get(DiscoveryRun, run_id)
            if run is None:
                return
            run.selected_count = len(results)
            run.succeeded_count = sum(result.get("status") == "completed" for result in results)
            run.failed_count = sum(result.get("status") == "failed" for result in results)
            session.commit()
        finally:
            session.close()
    @staticmethod
    def _disabled_result() -> dict[str, Any]:
        logger.info("scheduler_disabled")
        return {"status": "disabled", "results": []}