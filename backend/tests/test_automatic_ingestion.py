from datetime import datetime, timedelta, timezone
from threading import Event, Thread
from urllib.error import URLError

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
        assert second["automatic_ingestion"]["attempted"] == 1
        assert second["automatic_ingestion"]["succeeded"] == 1
        assert second["automatic_ingestion"]["skipped"] == 0
        assert second["automatic_ingestion"]["results"][0]["skipped_duplicates"] == 2
        db = SessionLocal()
        try:
            assert db.query(Job).count() == 2
            automatic_runs = db.query(IngestionRun).filter_by(is_automatic=True).all()
            assert len(automatic_runs) == 2
            assert all(run.fetched == 2 and run.status == "completed" for run in automatic_runs)
            latest_run = db.query(DiscoveryRun).order_by(DiscoveryRun.id.desc()).first()
            assert latest_run.selected_count == 1
            assert latest_run.succeeded_count == 1
            assert latest_run.failed_count == 0
            assert latest_run.automatic_ingestion_health_results[0]["event"] == "run_started"
            completed_event = latest_run.automatic_ingestion_health_results[-1]
            assert completed_event["event"] == "run_completed"
            assert completed_event["attempted_count"] == 1
            assert completed_event["skipped_count"] == 0
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
            assert "failed_entered_cooldown" in [event["event"] for event in result["health_events"]]

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
    assert "selected_recovery" in [event["event"] for event in automatic["health_events"]]
    assert "recovery_attempted" in [event["event"] for event in automatic["health_events"]]
    assert "recovered" in [event["event"] for event in automatic["health_events"]]

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


def test_overlapping_automatic_runs_are_skipped_but_explicit_sources_still_run(tmp_path):
    _clean()
    now = datetime(2026, 10, 1, 12, tzinfo=timezone.utc)
    first_registry = SourceRegistry()
    _validated_source(first_registry, "automatic-source", now.replace(tzinfo=None))
    second_registry = SourceRegistry()
    second_registry.register_discovered("ashby", "automatic-source")
    second_registry.register_ashby_board("explicit-source")
    automatic_started = Event()
    release_automatic = Event()
    calls: list[str] = []

    class FakeIngestion:
        def __init__(self, _session, **_kwargs):
            pass

        def ingest(self, _source, identifier, **kwargs):
            if identifier == "automatic-source":
                assert kwargs["automatic"] is True
                calls.append("automatic")
                automatic_started.set()
                release_automatic.wait(timeout=3)
            else:
                calls.append("explicit")
            return {"status": "completed"}

    lock_path = str(tmp_path / "automatic-ingestion.lock")
    scheduler_options = {
        "settings": SchedulerSettings(enabled=True),
        "session_factory": SessionLocal,
        "ingestion_service_factory": FakeIngestion,
        "automatic_ingestion_enabled": True,
        "discovery_candidates": [],
        "discovery_providers": [],
        "clock": lambda: now,
        "automatic_run_lock_path": lock_path,
    }
    first_scheduler = SchedulerService(registry=first_registry, **scheduler_options)
    second_scheduler = SchedulerService(registry=second_registry, **scheduler_options)
    first_results: list[dict] = []
    first_thread = Thread(target=lambda: first_results.append(first_scheduler.run_cycle()))
    first_thread.start()
    try:
        assert automatic_started.wait(timeout=3)
        second_result = second_scheduler.run_cycle()
    finally:
        release_automatic.set()
        first_thread.join(timeout=3)

    assert not first_thread.is_alive()
    assert calls.count("automatic") == 1
    assert calls.count("explicit") == 1
    assert second_result["results"][0]["status"] == "completed"
    assert second_result["automatic_ingestion"]["status"] == "skipped_overlap"
    assert first_results[0]["automatic_ingestion"]["attempted"] == 1
    _clean()


def test_stale_automatic_runs_recover_without_touching_explicit_ingestion_runs(tmp_path):
    _clean()
    now = datetime(2026, 10, 1, 12, tzinfo=timezone.utc)
    stale_started_at = now - timedelta(hours=2)
    registry = SourceRegistry()
    _validated_source(registry, "stale-source", stale_started_at.replace(tzinfo=None))
    _set_source_health("stale-source", 2, error="previous failure")
    _validated_source(registry, "recent-source", (now - timedelta(minutes=1)).replace(tzinfo=None))
    _set_source_health("recent-source", 3, now - timedelta(minutes=30))

    db = SessionLocal()
    try:
        stale_discovery = DiscoveryRun(
            run_type="automatic_ingestion",
            started_at=stale_started_at.replace(tzinfo=None),
            status="running",
            automatic_ingestion_health_results=[{"event": "run_started"}],
        )
        db.add(stale_discovery)
        automatic_run = IngestionRun(
            source="ashby",
            source_identifier="stale-source",
            is_automatic=True,
            started_at=stale_started_at.replace(tzinfo=None),
            status="running",
        )
        explicit_run = IngestionRun(
            source="ashby",
            source_identifier="stale-source",
            is_automatic=False,
            started_at=stale_started_at.replace(tzinfo=None),
            status="running",
        )
        recent_discovery = DiscoveryRun(
            run_type="automatic_ingestion",
            started_at=(now - timedelta(minutes=1)).replace(tzinfo=None),
            status="running",
            automatic_ingestion_health_results=[{"event": "run_started"}],
        )
        recent_automatic_run = IngestionRun(
            source="ashby",
            source_identifier="recent-source",
            is_automatic=True,
            started_at=(now - timedelta(minutes=1)).replace(tzinfo=None),
            status="running",
        )
        db.add_all([automatic_run, explicit_run, recent_discovery, recent_automatic_run])
        db.commit()
        stale_discovery_id = stale_discovery.id
        automatic_run_id = automatic_run.id
        explicit_run_id = explicit_run.id
        recent_discovery_id = recent_discovery.id
        recent_automatic_run_id = recent_automatic_run.id
    finally:
        db.close()

    class FakeIngestion:
        def __init__(self, _session, **_kwargs):
            pass

        def ingest(self, *_args, **_kwargs):
            raise AssertionError("active cooldown must exclude the stale source")

    scheduler = SchedulerService(
        settings=SchedulerSettings(enabled=True),
        registry=registry,
        ingestion_service_factory=FakeIngestion,
        automatic_ingestion_enabled=True,
        discovery_candidates=[],
        discovery_providers=[],
        clock=lambda: now,
        automatic_run_lock_path=str(tmp_path / "stale-recovery.lock"),
    )
    result = scheduler.run_cycle()["automatic_ingestion"]
    assert result["selected"] == 0
    assert "skipped_cooldown_active" in [event["event"] for event in result["health_events"]]

    db = SessionLocal()
    try:
        stale_discovery = db.get(DiscoveryRun, stale_discovery_id)
        automatic_run = db.get(IngestionRun, automatic_run_id)
        explicit_run = db.get(IngestionRun, explicit_run_id)
        recent_discovery = db.get(DiscoveryRun, recent_discovery_id)
        recent_automatic_run = db.get(IngestionRun, recent_automatic_run_id)
        health = db.query(DiscoveredSource).filter_by(identifier="stale-source").one()
        assert stale_discovery.status == "failed"
        assert any(event["event"] == "run_interrupted" for event in stale_discovery.automatic_ingestion_health_results)
        assert automatic_run.status == "failed"
        assert "interrupted by process restart" in automatic_run.message
        assert explicit_run.status == "running"
        assert recent_discovery.status == "running"
        assert recent_automatic_run.status == "running"
        assert health.consecutive_automatic_ingestion_failures == 3
        assert health.automatic_ingestion_cooldown_started_at.replace(tzinfo=timezone.utc) == now
        current_run = db.query(DiscoveryRun).filter(
            DiscoveryRun.run_type == "automatic_ingestion",
            DiscoveryRun.status == "completed",
        ).one()
        assert current_run.selected_count == 0
        assert current_run.failed_count == 0
        assert current_run.automatic_ingestion_health_results[-1]["event"] == "run_completed"
    finally:
        db.close()
    _clean()


def test_timeout_and_malformed_sources_fail_independently_with_safe_audit(caplog):
    _clean()
    now = datetime(2026, 10, 1, 12, tzinfo=timezone.utc)
    registry = SourceRegistry()
    _validated_source(registry, "timeout-source", now.replace(tzinfo=None))
    _validated_source(registry, "malformed-source", (now - timedelta(seconds=1)).replace(tzinfo=None))
    _validated_source(registry, "healthy-source", (now - timedelta(seconds=2)).replace(tzinfo=None))
    calls: list[str] = []

    class FakeIngestion:
        def __init__(self, _session, **_kwargs):
            pass

        def ingest(self, _source, identifier, **kwargs):
            assert kwargs == {"max_jobs": 4, "timeout_seconds": 9, "automatic": True}
            calls.append(identifier)
            if identifier == "timeout-source":
                raise URLError(TimeoutError("Authorization: Bearer timeout-secret"))
            if identifier == "malformed-source":
                raise ValueError("Malformed connector response")
            return {"status": "completed"}

    scheduler = SchedulerService(
        settings=SchedulerSettings(enabled=True),
        registry=registry,
        ingestion_service_factory=FakeIngestion,
        automatic_ingestion_enabled=True,
        max_automatic_sources=10,
        max_automatic_jobs=4,
        automatic_timeout_seconds=9,
        discovery_candidates=[],
        discovery_providers=[],
        clock=lambda: now,
    )
    automatic = scheduler.run_cycle()["automatic_ingestion"]
    assert calls == ["timeout-source", "malformed-source", "healthy-source"]
    assert automatic["attempted"] == 3
    assert automatic["failed"] == 2
    assert automatic["succeeded"] == 1
    by_source = dict(zip(calls, automatic["results"], strict=True))
    assert by_source["timeout-source"]["is_timeout"] is True
    assert "timeout-secret" not in by_source["timeout-source"]["message"]
    assert "[REDACTED]" in by_source["timeout-source"]["message"]
    assert by_source["malformed-source"]["is_timeout"] is False
    assert "timeout-secret" not in caplog.text
    assert "source_timeout" in [event["event"] for event in automatic["health_events"]]
    assert "source_failed" in [event["event"] for event in automatic["health_events"]]
    timeout_event = next(event for event in automatic["health_events"] if event["event"] == "source_timeout")
    assert timeout_event["health_state"] == "degraded"
    assert _source_health("timeout-source").consecutive_automatic_ingestion_failures == 1
    assert _source_health("malformed-source").consecutive_automatic_ingestion_failures == 1
    assert _source_health("healthy-source").consecutive_automatic_ingestion_failures == 0
    db = SessionLocal()
    try:
        run = db.query(DiscoveryRun).filter_by(run_type="automatic_ingestion").one()
        assert run.status == "completed"
        assert run.selected_count == 3
        assert run.succeeded_count == 1
        assert run.failed_count == 2
        final_event = run.automatic_ingestion_health_results[-1]
        assert final_event["event"] == "run_completed"
        assert final_event["attempted_count"] == 3
        assert final_event["skipped_count"] == 0
    finally:
        db.close()
    _clean()


def test_duplicate_selected_source_is_attempted_once_and_audited_as_skipped(tmp_path):
    _clean()
    registry = SourceRegistry()
    now = datetime(2026, 10, 1, 12, tzinfo=timezone.utc)
    _validated_source(registry, "duplicate-source", now.replace(tzinfo=None))
    _set_source_health("duplicate-source", 3, now - timedelta(seconds=3601))
    configuration = registry.resolve("ashby", "duplicate-source")
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
        automatic_run_lock_path=str(tmp_path / "duplicate-attempt.lock"),
    )
    key = ("ashby", "duplicate-source")
    scheduler._select_automatic_sources = lambda _configured: (
        [configuration, configuration],
        {key},
        [],
        {key: 3},
    )  # type: ignore[method-assign]

    automatic = scheduler.run_cycle()["automatic_ingestion"]
    assert calls == ["duplicate-source"]
    assert automatic["selected"] == 1
    assert automatic["attempted"] == 1
    assert automatic["skipped"] == 1
    assert "skipped_duplicate_selection" in [event["event"] for event in automatic["health_events"]]
    assert [event["event"] for event in automatic["health_events"]].count("recovery_attempted") == 1
    assert _source_health("duplicate-source").consecutive_automatic_ingestion_failures == 0
    _clean()
