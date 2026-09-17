from datetime import datetime
from threading import Event, Thread
from zoneinfo import ZoneInfo

from app.connectors.source_registry import SourceConfiguration, SourceRegistry
from app.services.scheduler_service import SchedulerService, SchedulerSettings
import app.services.scheduler_service as scheduler_module


class _Session:
    def close(self) -> None:
        return None


def _registry(*identifiers: str) -> SourceRegistry:
    registry = SourceRegistry()
    for identifier in identifiers:
        registry.register(
            SourceConfiguration(
                source="test-source",
                identifier=identifier,
                enabled=True,
                connector_factory=object,
            )
        )
    return registry


def test_scheduler_configuration_defaults_to_safe_disabled_eastern_schedule():
    settings = SchedulerSettings()

    assert settings.enabled is False
    assert settings.hour == 5
    assert settings.minute == 0
    assert settings.timezone == "America/New_York"
    assert settings.zone == ZoneInfo("America/New_York")


def test_scheduler_rejects_invalid_timezone_and_time():
    for kwargs in ({"timezone": "Not/AZone"}, {"hour": 24}, {"minute": 60}):
        try:
            SchedulerSettings(**kwargs)
        except ValueError:
            pass
        else:
            raise AssertionError("Invalid scheduler settings should be rejected")


def test_scheduler_disabled_does_not_invoke_ingestion():
    calls: list[str] = []

    class FakeIngestion:
        def __init__(self, *_args, **_kwargs):
            calls.append("constructed")

    scheduler = SchedulerService(
        settings=SchedulerSettings(enabled=False),
        registry=_registry("one"),
        session_factory=_Session,
        ingestion_service_factory=FakeIngestion,
    )

    assert scheduler.trigger_manual() == {"status": "disabled", "results": []}
    assert calls == []


def test_scheduler_processes_only_enabled_sources_and_calls_ingestion_service():
    registry = _registry("one")
    registry.register(
        SourceConfiguration(
            source="test-source",
            identifier="disabled",
            enabled=False,
            connector_factory=object,
        )
    )
    calls: list[tuple[str, str]] = []

    class FakeIngestion:
        def __init__(self, _session, registry):
            assert registry is not None

        def ingest(self, source: str, identifier: str):
            calls.append((source, identifier))
            return {"source": source, "source_identifier": identifier, "status": "completed"}

    scheduler = SchedulerService(
        settings=SchedulerSettings(enabled=True),
        registry=registry,
        session_factory=_Session,
        ingestion_service_factory=FakeIngestion,
    )

    result = scheduler.trigger_manual()

    assert calls == [("test-source", "one")]
    assert result["status"] == "completed"
    assert len(result["results"]) == 1


def test_scheduler_isolates_source_failure_and_continues():
    calls: list[str] = []

    class FakeIngestion:
        def __init__(self, _session, **_kwargs):
            pass

        def ingest(self, _source: str, identifier: str):
            calls.append(identifier)
            if identifier == "one":
                raise RuntimeError("source unavailable")
            return {"source_identifier": identifier, "status": "completed"}

    scheduler = SchedulerService(
        settings=SchedulerSettings(enabled=True),
        registry=_registry("one", "two"),
        session_factory=_Session,
        ingestion_service_factory=FakeIngestion,
    )

    result = scheduler.run_cycle()

    assert calls == ["one", "two"]
    assert result["results"][0]["status"] == "failed"
    assert "source unavailable" in result["results"][0]["message"]
    assert result["results"][1]["status"] == "completed"


def test_scheduler_prevents_overlapping_runs_for_same_source():
    started = Event()
    release = Event()
    calls = 0

    class FakeIngestion:
        def __init__(self, _session, **_kwargs):
            pass

        def ingest(self, _source: str, _identifier: str):
            nonlocal calls
            calls += 1
            started.set()
            release.wait(timeout=2)
            return {"status": "completed"}

    scheduler = SchedulerService(
        settings=SchedulerSettings(enabled=True),
        registry=_registry("one"),
        session_factory=_Session,
        ingestion_service_factory=FakeIngestion,
    )
    first_result: list[dict] = []
    first = Thread(target=lambda: first_result.append(scheduler.run_cycle()))
    first.start()
    assert started.wait(timeout=2)

    second = scheduler.run_cycle()
    release.set()
    first.join(timeout=2)

    assert calls == 1
    assert second["results"][0]["status"] == "skipped_overlap"
    assert first_result[0]["results"][0]["status"] == "completed"


def test_scheduler_uses_explicit_timezone_for_next_run_and_due_cycle():
    scheduler = SchedulerService(
        settings=SchedulerSettings(enabled=True),
        registry=SourceRegistry(),
        session_factory=_Session,
    )
    after_dst = datetime(2026, 7, 1, 8, 0, tzinfo=ZoneInfo("UTC"))
    next_run = scheduler.next_run_at(after_dst)

    assert next_run.tzinfo == ZoneInfo("America/New_York")
    assert next_run.hour == 5
    assert next_run.utcoffset().total_seconds() == -4 * 60 * 60
    assert scheduler.run_if_due(datetime(2026, 7, 1, 8, 59, tzinfo=ZoneInfo("UTC")))["status"] == "not_due"
    assert scheduler.run_if_due(datetime(2026, 7, 1, 9, 0, tzinfo=ZoneInfo("UTC")))["status"] == "completed"
    assert scheduler.run_if_due(datetime(2026, 7, 1, 10, 0, tzinfo=ZoneInfo("UTC")))["status"] == "not_due"


def test_manual_trigger_uses_same_cycle_path():
    scheduler = SchedulerService(settings=SchedulerSettings(enabled=True), registry=SourceRegistry())
    cycle_calls: list[str] = []

    def fake_cycle():
        cycle_calls.append("cycle")
        return {"status": "completed", "results": []}

    scheduler.run_cycle = fake_cycle  # type: ignore[method-assign]
    assert scheduler.trigger_manual()["status"] == "completed"
    assert cycle_calls == ["cycle"]


def test_scheduler_module_import_does_not_start_a_scheduler():
    assert not any(isinstance(value, SchedulerService) for value in vars(scheduler_module).values())