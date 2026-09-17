from unittest.mock import patch

from app.connectors.source_registry import SourceRegistry
from app.core.database import SessionLocal
from app.main import app  # noqa: F401
from app.models.discovered_source import DiscoveredSource
from app.models.discovery_run import DiscoveryRun
from app.services.scheduler_service import SchedulerService, SchedulerSettings
from app.services.source_discovery_service import DiscoveryCandidate, SourceDiscoveryService


def _clean() -> None:
    db = SessionLocal()
    try:
        db.query(DiscoveredSource).delete()
        db.query(DiscoveryRun).delete()
        db.commit()
    finally:
        db.close()


def test_discovery_validates_greenhouse_lever_and_ashby_and_promotes_sources():
    _clean()
    registry = SourceRegistry()
    service = SourceDiscoveryService(SessionLocal(), registry=registry)
    try:
        with patch.multiple(
            "app.services.source_discovery_service.GreenhouseConnector",
            fetch=lambda self: [{"id": "gh-job"}],
        ), patch.multiple(
            "app.services.source_discovery_service.LeverConnector",
            fetch=lambda self: [{"id": "lever-job"}],
        ), patch.multiple(
            "app.services.source_discovery_service.AshbyConnector",
            fetch=lambda self: [{"id": "ashby-job"}],
        ):
            result = service.discover([
                DiscoveryCandidate("greenhouse", "valid-gh", "Greenhouse Co"),
                DiscoveryCandidate("lever", "valid-lever", "Lever Co"),
                DiscoveryCandidate("ashby", "valid-ashby", "Ashby Co"),
            ])
        assert result["validated"] == 3
        assert len(registry.enabled_configurations()) == 3
        db = service.db
        assert db.query(DiscoveredSource).filter(DiscoveredSource.eligible.is_(True)).count() == 3
        assert db.query(DiscoveryRun).one().validated_count == 3
    finally:
        service.db.close()
        _clean()


def test_discovery_rejects_invalid_source_and_unreachable_board_with_reason():
    _clean()
    service = SourceDiscoveryService(SessionLocal(), registry=SourceRegistry())
    try:
        with patch("app.services.source_discovery_service.GreenhouseConnector.fetch", side_effect=TimeoutError("timed out")):
            result = service.discover([
                DiscoveryCandidate("unknown", "board"),
                DiscoveryCandidate("greenhouse", "unreachable"),
            ])
        assert result["validated"] == 0
        assert result["rejected"] == 2
        records = service.db.query(DiscoveredSource).all()
        assert len(records) == 2
        assert all(record.eligible is False and record.rejection_reason for record in records)
    finally:
        service.db.close()
        _clean()


def test_discovery_is_idempotent_for_same_source_and_identifier():
    _clean()
    service = SourceDiscoveryService(SessionLocal(), registry=SourceRegistry())
    candidate = DiscoveryCandidate("ashby", "repeatable")
    try:
        with patch("app.services.source_discovery_service.AshbyConnector.fetch", return_value=[]):
            service.discover([candidate])
            service.discover([candidate])
        assert service.db.query(DiscoveredSource).filter_by(source="ashby", identifier="repeatable").count() == 1
    finally:
        service.db.close()
        _clean()


def test_scheduler_runs_discovery_before_ingestion_without_breaking_isolation():
    _clean()
    registry = SourceRegistry()
    calls: list[str] = []

    class FakeDiscovery:
        def __init__(self, _session, registry):
            self.registry = registry

        def discover(self, candidates):
            calls.append(candidates[0].identifier)
            self.registry.register_ashby_board(candidates[0].identifier)
            return {"status": "completed", "validated": 1}

    class FakeIngestion:
        def __init__(self, _session, **_kwargs):
            pass

        def ingest(self, source, identifier):
            calls.append(f"ingest:{source}:{identifier}")
            return {"status": "completed"}

    scheduler = SchedulerService(
        settings=SchedulerSettings(enabled=True),
        registry=registry,
        session_factory=SessionLocal,
        ingestion_service_factory=FakeIngestion,
        discovery_service_factory=FakeDiscovery,
        discovery_candidates=[{"source": "ashby", "identifier": "scheduled-board"}],
    )
    try:
        result = scheduler.run_cycle()
        assert result["discovery"]["validated"] == 1
        assert calls == ["scheduled-board", "ingest:ashby:scheduled-board"]
    finally:
        _clean()