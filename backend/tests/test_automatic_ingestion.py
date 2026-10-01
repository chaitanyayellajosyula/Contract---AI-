from datetime import datetime, timedelta, timezone

from app.core.database import SessionLocal
from app.main import app  # noqa: F401
from app.models.discovered_source import DiscoveredSource
from app.models.discovery_run import DiscoveryRun
from app.models.ingestion_run import IngestionRun
from app.models.job import Job
from app.core.config import (
    AUTOMATIC_INGESTION_FAILURE_THRESHOLD,
    AUTOMATIC_INGESTION_HEALTH_COOLDOWN_SECONDS,
)
from app.services.scheduler_service import SchedulerService, SchedulerSettings
from app.connectors.source_registry import SourceRegistry


def _clean() -> None:
    db = SessionLocal()
    try:
        db.query(Job).delete()
        db.query(IngestionRun).delete()
        db.query(DiscoveredSource).delete()
        db.query(DiscoveryRun).delete()
        db.commit()
    finally:
        db.close()


def _validated_source(registry: SourceRegistry, identifier: str, validated_at: datetime) -> None:
    registry.register_discovered("ashby", identifier)
    db = SessionLocal()
    try:
        db.add(
            DiscoveredSource(
                source="ashby",
                identifier=identifier,
                jobs_endpoint=f"https://api.ashbyhq.com/posting-api/job-board/{identifier}",
                status="validated",
                validation_status="valid",
                eligible=True,
                first_discovered_at=validated_at,
                last_checked_at=validated_at,
                last_validated_at=validated_at,
            )
        )
        db.commit()
    finally:
        db.close()


def _job_payload(identifier: str, count: int = 1) -> list[dict]:
    return [
        {
            "id": f"{identifier}-{index}",
            "title": f"{identifier} Engineer {index}",
            "jobUrl": f"https://jobs.ashbyhq.com/{identifier}/{index}",
            "applyUrl": f"https://jobs.ashbyhq.com/{identifier}/{index}/application",
        }
        for index in range(count)
    ]


def _source_health(identifier: str) -> DiscoveredSource:
    db = SessionLocal()
    try:
        return db.query(DiscoveredSource).filter_by(source="ashby", identifier=identifier).one()
    finally:
        db.close()


def _set_source_health(
    identifier: str,
    failures: int,
    cooldown_started_at: datetime | None = None,
    error: str | None = "source unavailable",
) -> None:
    db = SessionLocal()
    try:
        record = db.query(DiscoveredSource).filter_by(source="ashby", identifier=identifier).one()
        record.consecutive_automatic_ingestion_failures = failures
        record.automatic_ingestion_cooldown_started_at = cooldown_started_at
        record.last_automatic_ingestion_error = error
        db.commit()
    finally:
        db.close()


def test_automatic_ingestion_disabled_does_not_select_discovered_sources(monkeypatch):
    _clean()
    registry = SourceRegistry()
    _validated_source(registry, "disabled-source", datetime.utcnow())
    calls: list[str] = []

    class FakeIngestion:
        def __init__(self, _session, **_kwargs):
            pass

        def ingest(self, source, identifier):
            calls.append(f"{source}:{identifier}")
            return {"status": "completed"}

    scheduler = SchedulerService(
        settings=SchedulerSettings(enabled=True),
        registry=registry,
        ingestion_service_factory=FakeIngestion,
        automatic_ingestion_enabled=False,
        discovery_candidates=[],
        discovery_providers=[],
    )
    result = scheduler.run_cycle()
    assert result["automatic_ingestion"]["selected"] == 0
    assert calls == []
    _clean()


def test_automatic_failure_threshold_defaults_to_three():
    scheduler = SchedulerService(automatic_ingestion_enabled=True)
    assert AUTOMATIC_INGESTION_FAILURE_THRESHOLD == 3
    assert scheduler.automatic_failure_threshold == 3
    assert AUTOMATIC_INGESTION_HEALTH_COOLDOWN_SECONDS == 3600
    assert scheduler.automatic_health_cooldown_seconds == 3600


def test_automatic_ingestion_selects_validated_sources_with_limits_and_is_idempotent(monkeypatch):
    _clean()
    registry = SourceRegistry()
    timestamp = datetime.utcnow()
    _validated_source(registry, "new-source", timestamp)
    _validated_source(registry, "older-source", datetime(2020, 1, 1))
    from app.connectors.ashby.ashby_connector import AshbyConnector

    original_fetch = AshbyConnector.fetch
    AshbyConnector.fetch = lambda self: _job_payload(self.board, 3)  # type: ignore[assignment]
    try:
        scheduler = SchedulerService(
            settings=SchedulerSettings(enabled=True),
            registry=registry,
            automatic_ingestion_enabled=True,
            max_automatic_sources=1,
            max_automatic_jobs=2,
            discovery_candidates=[],
            discovery_providers=[],
        )
        first = scheduler.run_cycle()
        second = scheduler.run_cycle()
        assert first["automatic_ingestion"]["selected"] == 1
        assert first["automatic_ingestion"]["succeeded"] == 1
        assert second["automatic_ingestion"]["selected"] == 1
        assert second["automatic_ingestion"]["succeeded"] == 1
        assert second["automatic_ingestion"]["results"][0]["skipped_duplicates"] == 2
        db = SessionLocal()
        try:
            assert db.query(Job).count() == 2
        finally:
            db.close()
    finally:
        AshbyConnector.fetch = original_fetch
        _clean()


def test_automatic_source_failure_does_not_stop_explicit_configured_ingestion():
    _clean()
    registry = SourceRegistry()
    registry.register_ashby_board("explicit-source")
    _validated_source(registry, "automatic-source", datetime.utcnow())
    calls: list[str] = []

    class FakeIngestion:
        def __init__(self, _session, **_kwargs):
            pass

        def ingest(self, source, identifier, **_kwargs):
            calls.append(identifier)
            if identifier == "automatic-source":
                raise RuntimeError("automatic source unavailable")
            return {"status": "completed", "created": 1}

    scheduler = SchedulerService(
        settings=SchedulerSettings(enabled=True),
        registry=registry,
        ingestion_service_factory=FakeIngestion,
        automatic_ingestion_enabled=True,
        max_automatic_sources=10,
        discovery_candidates=[],
        discovery_providers=[],
    )
    result = scheduler.run_cycle()
    assert calls == ["explicit-source", "automatic-source"]
    assert result["results"][0]["status"] == "completed"
    assert result["automatic_ingestion"]["failed"] == 1
    _clean()


def test_repeated_failures_skip_source_and_success_resets_health():
    _clean()
    registry = SourceRegistry()
    now = datetime(2026, 10, 1, 12, tzinfo=timezone.utc)
    _validated_source(registry, "flaky-source", now.replace(tzinfo=None))
    outcomes = [
        RuntimeError("authorization: Bearer top-secret"),
        RuntimeError("temporary failure"),
        RuntimeError("x" * 700),
        None,
        None,
    ]

    class FakeIngestion:
        def __init__(self, _session, **_kwargs):
            pass

        def ingest(self, _source, _identifier, **_kwargs):
            outcome = outcomes.pop(0)
            if outcome is not None:
                raise outcome
            return {"status": "completed", "created": 1}

    scheduler = SchedulerService(
        settings=SchedulerSettings(enabled=True),
        registry=registry,
        ingestion_service_factory=FakeIngestion,
        automatic_ingestion_enabled=True,
        discovery_candidates=[],
        discovery_providers=[],
        clock=lambda: now,
    )
    result = scheduler.run_cycle()["automatic_ingestion"]
    assert result["selected"] == 1
    assert result["failed"] == 1
    health = _source_health("flaky-source")
    assert health.consecutive_automatic_ingestion_failures == 1
    assert "top-secret" not in health.last_automatic_ingestion_error
    assert "[REDACTED]" in health.last_automatic_ingestion_error

    for expected_failures in (2, 3):
        result = scheduler.run_cycle()["automatic_ingestion"]
        assert result["selected"] == 1
        assert result["failed"] == 1
        assert _source_health("flaky-source").consecutive_automatic_ingestion_failures == expected_failures
        if expected_failures == 3:
            assert result["health_events"][-1]["event"] == "failed_entered_cooldown"

    health = _source_health("flaky-source")
    assert health.last_automatic_ingestion_attempt_at is not None
    assert health.last_automatic_ingestion_success_at is None
    assert len(health.last_automatic_ingestion_error) == 500
    assert health.automatic_ingestion_cooldown_started_at is not None

    skipped = scheduler.run_cycle()["automatic_ingestion"]
    assert skipped["selected"] == 0

    db = SessionLocal()
    try:
        record = db.query(DiscoveredSource).filter_by(identifier="flaky-source").one()
        record.consecutive_automatic_ingestion_failures = 2
        record.automatic_ingestion_cooldown_started_at = None
        db.commit()
    finally:
        db.close()
    below_threshold = scheduler.run_cycle()["automatic_ingestion"]
    assert below_threshold["selected"] == 1
    assert below_threshold["succeeded"] == 1

    health = _source_health("flaky-source")
    assert health.consecutive_automatic_ingestion_failures == 0
    assert health.last_automatic_ingestion_success_at is not None
    assert health.last_automatic_ingestion_error is None
    assert health.automatic_ingestion_cooldown_started_at is None
    assert scheduler.run_cycle()["automatic_ingestion"]["selected"] == 1
    _clean()


def test_active_cooldown_skips_repeated_runs_and_persists_audit_events():
    _clean()
    registry = SourceRegistry()
    now = datetime(2026, 10, 1, 12, tzinfo=timezone.utc)
    cooldown_started = now - timedelta(minutes=30)
    _validated_source(registry, "cooling-source", now.replace(tzinfo=None))
    _validated_source(registry, "healthy-source", (now - timedelta(minutes=1)).replace(tzinfo=None))
    _set_source_health("cooling-source", 3, cooldown_started)
    calls: list[str] = []

    class FakeIngestion:
        def __init__(self, _session, **_kwargs):
            pass

        def ingest(self, _source, identifier, **_kwargs):
            calls.append(identifier)
            return {"status": "completed"}

    scheduler = SchedulerService(
        settings=SchedulerSettings(enabled=True),
        registry=registry,
        ingestion_service_factory=FakeIngestion,
        automatic_ingestion_enabled=True,
        max_automatic_sources=1,
        discovery_candidates=[],
        discovery_providers=[],
        clock=lambda: now,
    )

    for _ in range(2):
        automatic = scheduler.run_cycle()["automatic_ingestion"]
        assert automatic["selected"] == 1
        assert "skipped_cooldown_active" in [event["event"] for event in automatic["health_events"]]
        cooldown_event = next(
            event for event in automatic["health_events"] if event["event"] == "skipped_cooldown_active"
        )
        assert cooldown_event["health_state"] == "unhealthy"
    assert calls == ["healthy-source", "healthy-source"]

    db = SessionLocal()
    try:
        health = db.query(DiscoveredSource).filter_by(identifier="cooling-source").one()
        runs = db.query(DiscoveryRun).order_by(DiscoveryRun.id).all()
        assert health.consecutive_automatic_ingestion_failures == 3
        assert health.automatic_ingestion_cooldown_started_at.replace(tzinfo=timezone.utc) == cooldown_started
        assert len(runs) == 2
        for run in runs:
            assert run.run_type == "automatic_ingestion"
            assert "skipped_cooldown_active" in [
                event["event"] for event in run.automatic_ingestion_health_results
            ]
    finally:
        db.close()
    _clean()


def test_expired_cooldown_allows_one_recovery_and_clears_health_state():
    _clean()
    registry = SourceRegistry()
    now = datetime(2026, 10, 1, 12, tzinfo=timezone.utc)
    _validated_source(registry, "recovering-source", now.replace(tzinfo=None))
    _set_source_health("recovering-source", 3, now - timedelta(seconds=3601))
    calls: list[str] = []

    class FakeIngestion:
        def __init__(self, _session, **_kwargs):
            pass

        def ingest(self, _source, identifier, **_kwargs):
            calls.append(identifier)
            return {"status": "completed"}

    scheduler = SchedulerService(
        settings=SchedulerSettings(enabled=True),
        registry=registry,
        ingestion_service_factory=FakeIngestion,
        automatic_ingestion_enabled=True,
        discovery_candidates=[],
        discovery_providers=[],
        clock=lambda: now,
    )
    automatic = scheduler.run_cycle()["automatic_ingestion"]
    assert calls == ["recovering-source"]
    assert automatic["selected"] == 1
    assert [event["event"] for event in automatic["health_events"]] == ["selected_recovery", "recovered"]

    health = _source_health("recovering-source")
    assert health.consecutive_automatic_ingestion_failures == 0
    assert health.last_automatic_ingestion_error is None
    assert health.automatic_ingestion_cooldown_started_at is None
    assert health.last_automatic_ingestion_attempt_at is not None
    assert health.last_automatic_ingestion_success_at is not None
    _clean()


def test_failed_recovery_restarts_cooldown_without_blocking_healthy_source(caplog):
    _clean()
    registry = SourceRegistry()
    now = datetime(2026, 10, 1, 12, tzinfo=timezone.utc)
    _validated_source(registry, "recovering-source", now.replace(tzinfo=None))
    _validated_source(registry, "healthy-source", (now - timedelta(minutes=1)).replace(tzinfo=None))
    _set_source_health("recovering-source", 3, now - timedelta(seconds=3601))
    calls: list[str] = []

    class FakeIngestion:
        def __init__(self, _session, **_kwargs):
            pass

        def ingest(self, _source, identifier, **_kwargs):
            calls.append(identifier)
            if identifier == "recovering-source":
                raise RuntimeError("Authorization: Bearer recovery-secret")
            return {"status": "completed"}

    scheduler = SchedulerService(
        settings=SchedulerSettings(enabled=True),
        registry=registry,
        ingestion_service_factory=FakeIngestion,
        automatic_ingestion_enabled=True,
        discovery_candidates=[],
        discovery_providers=[],
        clock=lambda: now,
    )
    automatic = scheduler.run_cycle()["automatic_ingestion"]
    assert calls == ["recovering-source", "healthy-source"]
    assert automatic["failed"] == 1
    assert automatic["succeeded"] == 1
    assert "recovery_failed_cooldown_restarted" in [event["event"] for event in automatic["health_events"]]
    assert "recovery-secret" not in caplog.text

    failed_health = _source_health("recovering-source")
    assert failed_health.consecutive_automatic_ingestion_failures == 4
    assert "[REDACTED]" in failed_health.last_automatic_ingestion_error
    assert failed_health.automatic_ingestion_cooldown_started_at.replace(tzinfo=timezone.utc) == now
    assert _source_health("healthy-source").consecutive_automatic_ingestion_failures == 0
    retry = scheduler.run_cycle()["automatic_ingestion"]
    assert calls == ["recovering-source", "healthy-source", "healthy-source"]
    assert retry["selected"] == 1
    assert "skipped_cooldown_active" in [event["event"] for event in retry["health_events"]]
    _clean()


def test_configured_source_ignores_discovered_health_cooldown():
    _clean()
    registry = SourceRegistry()
    registry.register_ashby_board("explicit-cooling-source")
    now = datetime(2026, 10, 1, 12, tzinfo=timezone.utc)
    cooldown_started = now - timedelta(minutes=30)
    db = SessionLocal()
    try:
        db.add(DiscoveredSource(
            source="ashby",
            identifier="explicit-cooling-source",
            jobs_endpoint="https://api.ashbyhq.com/posting-api/job-board/explicit-cooling-source",
            status="validated",
            validation_status="valid",
            eligible=True,
            first_discovered_at=now.replace(tzinfo=None),
            last_checked_at=now.replace(tzinfo=None),
            last_validated_at=now.replace(tzinfo=None),
            consecutive_automatic_ingestion_failures=3,
            last_automatic_ingestion_error="still unavailable",
            automatic_ingestion_cooldown_started_at=cooldown_started,
        ))
        db.commit()
    finally:
        db.close()
    calls: list[str] = []

    class FakeIngestion:
        def __init__(self, _session, **_kwargs):
            pass

        def ingest(self, _source, identifier, **_kwargs):
            calls.append(identifier)
            return {"status": "completed"}

    scheduler = SchedulerService(
        settings=SchedulerSettings(enabled=True),
        registry=registry,
        ingestion_service_factory=FakeIngestion,
        automatic_ingestion_enabled=True,
        discovery_candidates=[],
        discovery_providers=[],
        clock=lambda: now,
    )
    result = scheduler.run_cycle()
    assert calls == ["explicit-cooling-source"]
    assert result["results"][0]["status"] == "completed"
    assert result["automatic_ingestion"]["selected"] == 0
    health = _source_health("explicit-cooling-source")
    assert health.consecutive_automatic_ingestion_failures == 3
    assert health.last_automatic_ingestion_error == "still unavailable"
    _clean()


def test_one_automatic_failure_does_not_stop_other_selected_sources():
    _clean()
    registry = SourceRegistry()
    timestamp = datetime.utcnow()
    _validated_source(registry, "broken-source", timestamp)
    _validated_source(registry, "healthy-source", timestamp.replace(microsecond=max(0, timestamp.microsecond - 1)))
    _validated_source(registry, "unhealthy-source", timestamp.replace(microsecond=max(0, timestamp.microsecond - 2)))
    db = SessionLocal()
    try:
        unhealthy = db.query(DiscoveredSource).filter_by(identifier="unhealthy-source").one()
        unhealthy.consecutive_automatic_ingestion_failures = 3
        db.commit()
    finally:
        db.close()
    calls: list[str] = []

    class FakeIngestion:
        def __init__(self, _session, **_kwargs):
            pass

        def ingest(self, _source, identifier, **_kwargs):
            calls.append(identifier)
            if identifier == "broken-source":
                raise RuntimeError("source unavailable")
            return {"status": "completed"}

    scheduler = SchedulerService(
        settings=SchedulerSettings(enabled=True),
        registry=registry,
        ingestion_service_factory=FakeIngestion,
        automatic_ingestion_enabled=True,
        discovery_candidates=[],
        discovery_providers=[],
    )
    result = scheduler.run_cycle()["automatic_ingestion"]
    assert calls == ["broken-source", "healthy-source"]
    assert len(calls) == len(set(calls))
    assert result["selected"] == 2
    assert result["failed"] == 1
    assert result["succeeded"] == 1
    assert _source_health("healthy-source").consecutive_automatic_ingestion_failures == 0
    _clean()
