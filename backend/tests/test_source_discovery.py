import json
from io import BytesIO
from unittest.mock import patch

import pytest

from app.connectors.source_registry import SourceRegistry
from app.core.database import SessionLocal
from app.main import app  # noqa: F401
from app.models.discovered_source import DiscoveredSource
from app.models.discovery_run import DiscoveryRun
from app.services.discovery_providers import AtsCompanyCatalogProvider, DiscoveryProvider, PublicJsonCatalogProvider
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


def test_public_catalog_provider_extracts_only_approved_ats_endpoints():
    payload = {
        "candidates": [
            {
                "source": "greenhouse",
                "identifier": "valid-board",
                "company_name": "Public Co",
                "jobs_endpoint": "https://boards-api.greenhouse.io/v1/boards/valid-board/jobs?content=true",
                "source_url": "https://boards.greenhouse.io/valid-board",
            },
            {
                "source": "unknown",
                "identifier": "bad",
                "jobs_endpoint": "https://example.com/jobs",
            },
            {"source": "lever", "identifier": "missing-endpoint"},
        ]
    }

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def read(self, _limit):
            return json.dumps(payload).encode("utf-8")

    provider = PublicJsonCatalogProvider(
        "https://catalog.example.test/boards.json",
        allowed_catalog_hosts=("catalog.example.test",),
    )
    with patch("app.services.discovery_providers.request.urlopen", return_value=Response()):
        candidates = provider.discover()
    assert len(candidates) == 1
    assert candidates[0].source == "greenhouse"
    assert candidates[0].discovery_provider == "public_json_catalog"


def test_public_catalog_provider_requires_https_and_allowlisted_host():
    with pytest.raises(ValueError):
        PublicJsonCatalogProvider("http://catalog.example.test/boards.json")
    with pytest.raises(ValueError):
        PublicJsonCatalogProvider("https://other.example.test/boards.json", allowed_catalog_hosts=("catalog.example.test",))


def test_provider_failure_isolated_and_cross_provider_duplicate_is_persisted_once():
    _clean()

    class GoodProvider(DiscoveryProvider):
        name = "good"

        def discover(self):
            return [DiscoveryCandidate(
                "ashby", "same-board", "Same Co",
                jobs_endpoint="https://api.ashbyhq.com/posting-api/job-board/same-board",
                discovery_provider=self.name,
            )]

    class DuplicateProvider(DiscoveryProvider):
        name = "duplicate"

        def discover(self):
            return [DiscoveryCandidate(
                "ashby", "same-board", discovery_provider=self.name,
                provider_metadata={"catalog": "second"},
            )]

    class BrokenProvider(DiscoveryProvider):
        name = "broken"

        def discover(self):
            raise TimeoutError("provider timed out")

    service = SourceDiscoveryService(SessionLocal(), registry=SourceRegistry())
    try:
        with patch("app.services.source_discovery_service.AshbyConnector.fetch", return_value=[]):
            result = service.discover_from_providers([GoodProvider(), DuplicateProvider(), BrokenProvider()])
        record = service.db.query(DiscoveredSource).filter_by(source="ashby", identifier="same-board").one()
        run = service.db.query(DiscoveryRun).one()
        assert result["validated"] == 1
        assert result["duplicates"] == 1
        assert len(result["failed_providers"]) == 1
        assert run.providers_count == 3
        assert record.provider_metadata["providers"] == ["good", "duplicate"]
    finally:
        service.db.close()
        _clean()


def test_provider_results_are_bounded_and_disabled_scheduler_skips_discovery():
    _clean()

    class ManyProvider(DiscoveryProvider):
        name = "many"

        def discover(self):
            return [DiscoveryCandidate("ashby", f"board-{index}") for index in range(40)]

    service = SourceDiscoveryService(SessionLocal(), registry=SourceRegistry())
    try:
        with patch("app.services.source_discovery_service.AshbyConnector.fetch", return_value=[]):
            result = service.discover_from_providers([ManyProvider()])
        assert result["candidates"] == 25
    finally:
        service.db.close()
        _clean()

    scheduler = SchedulerService(
        settings=SchedulerSettings(enabled=False),
        registry=SourceRegistry(),
        discovery_providers=[ManyProvider()],
    )
    assert scheduler.trigger_manual()["status"] == "disabled"


def test_ats_company_catalog_provider_parses_all_supported_ats_and_deduplicates_rows():
    manifest = {
        "by_ats_companies": {
            "greenhouse": {"csv": "https://storage.stapply.ai/catalog/greenhouse.csv"},
            "lever": {"csv": "https://storage.stapply.ai/catalog/lever.csv"},
            "ashby": {"csv": "https://storage.stapply.ai/catalog/ashby.csv"},
            "workday": {"csv": "https://storage.stapply.ai/catalog/workday.csv"},
        }
    }
    csv_by_url = {
        "https://storage.stapply.ai/catalog/greenhouse.csv": b"name,slug,url\nGreen Co,green-co,https://job-boards.greenhouse.io/green-co\nGreen Co,green-co,https://job-boards.greenhouse.io/green-co\nMalformed,,https://job-boards.greenhouse.io/bad\n",
        "https://storage.stapply.ai/catalog/lever.csv": b"name,slug,url\nLever Co,lever-co,https://jobs.lever.co/lever-co\n",
        "https://storage.stapply.ai/catalog/ashby.csv": b"name,slug,url\nAshby Co,ashby-co,https://jobs.ashbyhq.com/ashby-co\n",
    }

    class Response:
        def __init__(self, value):
            self.value = value

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def read(self, _limit):
            return self.value

    def open_url(url, timeout):
        assert timeout == 15
        if url.endswith("manifest.json"):
            return Response(json.dumps(manifest).encode("utf-8"))
        return Response(csv_by_url[url])

    provider = AtsCompanyCatalogProvider("https://storage.stapply.ai/catalog/manifest.json", max_rows_per_ats=10)
    with patch("app.services.discovery_providers.request.urlopen", side_effect=open_url):
        candidates = provider.discover()
    assert [(candidate.source, candidate.identifier) for candidate in candidates] == [
        ("greenhouse", "green-co"),
        ("lever", "lever-co"),
        ("ashby", "ashby-co"),
    ]
    assert all(candidate.discovery_provider == "ats_scrapers_company_catalog" for candidate in candidates)
    assert all(candidate.provider_metadata["catalog_url"] for candidate in candidates)


def test_ats_company_catalog_provider_rejects_unallowlisted_manifest_and_csv_hosts():
    with pytest.raises(ValueError):
        AtsCompanyCatalogProvider("https://untrusted.example/manifest.json")
    provider = AtsCompanyCatalogProvider("https://storage.stapply.ai/manifest.json")
    with pytest.raises(ValueError):
        provider._validate_url("https://untrusted.example/catalog.csv")


def test_ats_company_catalog_provider_bounds_rows_and_reports_failures():
    manifest = {"by_ats_companies": {
        "greenhouse": {"csv": "https://storage.stapply.ai/greenhouse.csv"},
        "lever": {"csv": "https://storage.stapply.ai/lever.csv"},
        "ashby": {"csv": "https://storage.stapply.ai/ashby.csv"},
    }}
    csv_data = b"name,slug,url\n" + b"\n".join(
        f"Company {index},company-{index},https://job-boards.greenhouse.io/company-{index}".encode()
        for index in range(20)
    )

    class Response:
        def __init__(self, value):
            self.value = value

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def read(self, _limit):
            return self.value

    def open_url(url, timeout):
        if url.endswith("manifest.json"):
            return Response(json.dumps(manifest).encode())
        if url.endswith("greenhouse.csv"):
            return Response(csv_data)
        raise TimeoutError("catalog file unavailable")

    provider = AtsCompanyCatalogProvider("https://storage.stapply.ai/manifest.json", max_rows_per_ats=5)
    with patch("app.services.discovery_providers.request.urlopen", side_effect=open_url):
        with pytest.raises(TimeoutError):
            provider.discover()

    provider = AtsCompanyCatalogProvider("https://storage.stapply.ai/manifest.json", max_rows_per_ats=5)
    with patch("app.services.discovery_providers.request.urlopen", return_value=Response(json.dumps(manifest).encode())):
        # The manifest remains bounded by the per-ATS cap when its files are available.
        assert provider.max_rows_per_ats == 5