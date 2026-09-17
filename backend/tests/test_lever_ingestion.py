import json
from io import BytesIO
from unittest.mock import patch

from fastapi.testclient import TestClient
import pytest

from app.connectors.lever.lever_connector import LeverConnector
from app.connectors.source_registry import SourceRegistry, source_registry
from app.core.database import SessionLocal
from app.main import app
from app.models.ingestion_run import IngestionRun
from app.models.job import Job
from app.models.user import User
from app.services.auth_service import AuthService

client = TestClient(app)


class _Response:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def read(self):
        return BytesIO(json.dumps(self.payload).encode("utf-8")).read()


def _auth_headers() -> dict[str, str]:
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == "lever-ingest@example.com").first()
        if user is None:
            user = User(
                full_name="Lever Ingest User",
                email="lever-ingest@example.com",
                hashed_password=AuthService(db).hash_password("Password123!"),
                role="RECRUITER",
                is_active=True,
            )
            db.add(user)
            db.commit()
            db.refresh(user)
        return {"Authorization": f"Bearer {AuthService(db).create_access_token(user)}"}
    finally:
        db.close()


def _clean() -> None:
    db = SessionLocal()
    try:
        db.query(Job).delete()
        db.query(IngestionRun).delete()
        db.commit()
    finally:
        db.close()


def test_lever_connector_fetches_and_normalizes_public_payload():
    payload = [
        {
            "id": "lever-job-123",
            "text": "Senior Platform Engineer",
            "hostedUrl": "https://jobs.lever.co/acme/lever-job-123",
            "applyUrl": "https://jobs.lever.co/acme/lever-job-123/apply",
            "descriptionPlain": "Build reliable platform services.",
            "categories": {
                "location": "Remote - United States",
                "commitment": "Full-time",
            },
            "workplaceType": "remote",
            "createdAt": 1760000000000,
        }
    ]

    with patch("app.connectors.lever.lever_connector.request.urlopen", return_value=_Response(payload)) as open_url:
        connector = LeverConnector("acme")
        fetched = connector.fetch()

    normalized = connector.normalize_job(fetched[0])
    assert open_url.call_args.args[0] == "https://api.lever.co/v0/postings/acme?mode=json"
    assert normalized["source"] == "lever"
    assert normalized["source_job_id"] == "lever-job-123"
    assert normalized["source_url"] == "https://jobs.lever.co/acme/lever-job-123"
    assert normalized["title"] == "Senior Platform Engineer"
    assert normalized["location"] == "Remote - United States"
    assert normalized["description"] == "Build reliable platform services."
    assert normalized["employment_type"] == "Full-time"
    assert normalized["remote_type"] == "remote"
    assert normalized["posted_at"] is not None


def test_lever_registry_configuration_and_disabled_source():
    registry = SourceRegistry()
    registry.register_lever_site("acme", settings={"region": "us"})
    registry.register_lever_site("beta")
    registry.register_lever_site("disabled", enabled=False)

    configuration = registry.resolve("lever", "acme")
    assert configuration is not None
    assert configuration.connector_type == "lever"
    assert configuration.settings == {"region": "us"}
    assert configuration.connector_factory is LeverConnector
    assert registry.resolve("lever", "disabled") is None
    assert [item.identifier for item in registry.enabled_configurations()] == ["acme", "beta"]
    with pytest.raises(ValueError, match="Lever site is required"):
        registry.register_lever_site(" ")


def test_lever_ingestion_is_idempotent_and_updates_existing_job():
    _clean()
    source_registry.register_lever_site("acme")
    payload = {
        "id": "lever-job-456",
        "text": "Data Engineer",
        "hostedUrl": "https://jobs.lever.co/acme/lever-job-456",
        "descriptionPlain": "Original description",
        "categories": {"location": "New York, NY"},
        "createdAt": 1760000000000,
    }
    original_fetch = LeverConnector.fetch_jobs
    LeverConnector.fetch_jobs = classmethod(lambda cls, site: [payload])  # type: ignore[assignment]
    try:
        first = client.post("/jobs/ingest/lever?board=acme", headers=_auth_headers())
        assert first.status_code == 200, first.text
        assert first.json()["created"] == 1

        duplicate = client.post("/jobs/ingest/lever?board=acme", headers=_auth_headers())
        assert duplicate.status_code == 200, duplicate.text
        assert duplicate.json()["skipped_duplicates"] == 1

        LeverConnector.fetch_jobs = classmethod(  # type: ignore[assignment]
            lambda cls, site: [{**payload, "descriptionPlain": "Updated description"}]
        )
        updated = client.post("/jobs/ingest/lever?board=acme", headers=_auth_headers())
        assert updated.status_code == 200, updated.text
        assert updated.json()["updated"] == 1
    finally:
        LeverConnector.fetch_jobs = original_fetch
        _clean()