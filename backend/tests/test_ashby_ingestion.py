import json
from io import BytesIO
from unittest.mock import patch

import pytest

from app.connectors.ashby.ashby_connector import AshbyConnector
from app.connectors.source_registry import SourceRegistry, source_registry
from app.core.database import SessionLocal
from app.main import app
from app.models.ingestion_run import IngestionRun
from app.models.job import Job
from fastapi.testclient import TestClient
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
        user = db.query(User).filter(User.email == "ashby-ingest@example.com").first()
        if user is None:
            user = User(
                full_name="Ashby Ingest User",
                email="ashby-ingest@example.com",
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


def test_ashby_connector_fetches_and_normalizes_public_payload():
    payload = {
        "jobs": [
            {
                "id": "ashby-job-123",
                "title": "Contract Platform Engineer",
                "employmentType": "Contract",
                "location": "Remote (US)",
                "workplaceType": "Remote",
                "isRemote": True,
                "publishedAt": "2026-09-10T12:00:00+00:00",
                "jobUrl": "https://jobs.ashbyhq.com/ramp/ashby-job-123",
                "applyUrl": "https://jobs.ashbyhq.com/ramp/ashby-job-123/application",
                "descriptionHtml": "<p>Build contract systems.</p>",
                "department": "Engineering",
                "team": "Platform",
                "secondaryLocations": [{"location": "Remote (US)"}],
            }
        ]
    }

    with patch("app.connectors.ashby.ashby_connector.request.urlopen", return_value=_Response(payload)) as open_url:
        connector = AshbyConnector("ramp")
        fetched = connector.fetch()

    normalized = connector.normalize_job(fetched[0])
    assert open_url.call_args.args[0] == "https://api.ashbyhq.com/posting-api/job-board/ramp"
    assert normalized["source"] == "ashby"
    assert normalized["source_job_id"] == "ashby-job-123"
    assert normalized["source_url"].endswith("ashby-job-123")
    assert normalized["apply_url"].endswith("/application")
    assert normalized["employment_type"] == "contract"
    assert normalized["remote_type"] == "remote"
    assert normalized["source_metadata"]["department"] == "Engineering"
    assert normalized["posted_at"].year == 2026


def test_ashby_registry_supports_multiple_real_boards_and_rejects_blank():
    registry = SourceRegistry()
    registry.register_ashby_board("ramp")
    registry.register_ashby_board("openai")

    assert [item.identifier for item in registry.enabled_configurations()] == ["ramp", "openai"]
    assert registry.resolve("ashby", "ramp").connector_type == "ashby"
    with pytest.raises(ValueError, match="Ashby board is required"):
        registry.register_ashby_board(" ")


def test_ashby_normalization_rejects_missing_identity_and_preserves_optional_gaps():
    with pytest.raises(ValueError, match="Ashby job id is required"):
        AshbyConnector.normalize_job({"title": "Missing ID", "jobUrl": "https://example.test/job"})

    normalized = AshbyConnector.normalize_job(
        {
            "id": "ashby-minimal",
            "title": "Minimal Job",
            "jobUrl": "https://jobs.ashbyhq.com/ramp/ashby-minimal",
        }
    )
    assert normalized["description"] is None
    assert normalized["location"] is None
    assert normalized["apply_url"] is None
    assert normalized["employment_type"] is None


def test_ashby_ingestion_is_idempotent_and_updates_existing_job():
    _clean()
    source_registry.register_ashby_board("ramp")
    payload = {
        "id": "ashby-job-456",
        "title": "Platform Engineer",
        "employmentType": "FullTime",
        "jobUrl": "https://jobs.ashbyhq.com/ramp/ashby-job-456",
        "applyUrl": "https://jobs.ashbyhq.com/ramp/ashby-job-456/application",
        "descriptionHtml": "Original",
        "publishedAt": "2026-09-10T12:00:00+00:00",
    }
    original_fetch = AshbyConnector.fetch_jobs
    AshbyConnector.fetch_jobs = classmethod(lambda cls, board: [payload])  # type: ignore[assignment]
    try:
        first = client.post("/jobs/ingest/ashby?board=ramp", headers=_auth_headers())
        assert first.status_code == 200, first.text
        assert first.json()["created"] == 1
        duplicate = client.post("/jobs/ingest/ashby?board=ramp", headers=_auth_headers())
        assert duplicate.json()["skipped_duplicates"] == 1
        AshbyConnector.fetch_jobs = classmethod(  # type: ignore[assignment]
            lambda cls, board: [{**payload, "descriptionHtml": "Updated"}]
        )
        updated = client.post("/jobs/ingest/ashby?board=ramp", headers=_auth_headers())
        assert updated.json()["updated"] == 1
    finally:
        AshbyConnector.fetch_jobs = original_fetch
        _clean()