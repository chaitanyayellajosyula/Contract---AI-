from fastapi.testclient import TestClient

from app.core.database import SessionLocal
from app.main import app
from app.models.job import Job
from app.models.ingestion_run import IngestionRun
from app.models.user import User
from app.services.auth_service import AuthService

client = TestClient(app)


def _auth_headers(email: str = "ingest@example.com") -> dict[str, str]:
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        if user is None:
            user = User(
                full_name="Ingest User",
                email=email,
                hashed_password=AuthService(db).hash_password("Password123!"),
                role="RECRUITER",
                is_active=True,
            )
            db.add(user)
            db.commit()
            db.refresh(user)
        token = AuthService(db).create_access_token(user)
        return {"Authorization": f"Bearer {token}"}
    finally:
        db.close()


def _clean_jobs() -> None:
    db = SessionLocal()
    try:
        db.query(Job).delete()
        db.commit()
    finally:
        db.close()


def _clean_ingestion_runs() -> None:
    db = SessionLocal()
    try:
        db.query(IngestionRun).delete()
        db.commit()
    finally:
        db.close()


def test_greenhouse_connector_normalizes_payload():
    from app.connectors.greenhouse.greenhouse_connector import GreenhouseConnector

    payload = {
        "id": 8123456,
        "title": "Senior Backend Engineer",
        "content": "<p>Build APIs and data pipelines.</p>",
        "location": {"name": "Remote, US"},
        "absolute_url": "https://stripe.com/jobs/search?gh_jid=8123456",
        "first_published": "2026-09-01T12:00:00Z",
        "application_deadline": "2026-09-30T00:00:00Z",
    }

    normalized = GreenhouseConnector.normalize_job(payload)
    assert normalized["title"] == "Senior Backend Engineer"
    assert normalized["source"] == "greenhouse"
    assert normalized["source_job_id"] == "8123456"
    assert normalized["source_url"] == "https://stripe.com/jobs/search?gh_jid=8123456"
    assert normalized["location"] == "Remote, US"
    assert normalized["remote_type"] == "remote"


def test_ingest_endpoint_creates_and_deduplicates_jobs():
    _clean_jobs()

    from app.connectors.greenhouse.greenhouse_connector import GreenhouseConnector

    job_payload = {
        "id": 9123456,
        "title": "Platform Engineer",
        "content": "<p>Ship backend systems.</p>",
        "location": {"name": "New York, NY"},
        "absolute_url": "https://stripe.com/jobs/search?gh_jid=9123456",
        "first_published": "2026-09-02T10:00:00Z",
    }

    total = [job_payload, {**job_payload, "id": 9123457, "title": "Platform Engineer 2", "absolute_url": "https://stripe.com/jobs/search?gh_jid=9123457"}]

    original_fetch = GreenhouseConnector.fetch_jobs
    GreenhouseConnector.fetch_jobs = classmethod(lambda cls, board: total)  # type: ignore[assignment]
    try:
        response = client.post("/jobs/ingest/greenhouse?board=stripe", headers=_auth_headers())
        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["source"] == "greenhouse"
        assert payload["fetched"] == 2
        assert payload["created"] == 2
        assert payload["skipped_duplicates"] == 0

        second = client.post("/jobs/ingest/greenhouse?board=stripe", headers=_auth_headers())
        assert second.status_code == 200, second.text
        second_payload = second.json()
        assert second_payload["created"] == 0
        assert second_payload["skipped_duplicates"] == 2

        list_response = client.get("/jobs", headers=_auth_headers())
        assert list_response.status_code == 200
        jobs = list_response.json()
        assert any(job["source_job_id"] == "9123456" for job in jobs)
    finally:
        GreenhouseConnector.fetch_jobs = original_fetch
        _clean_jobs()


def test_ingest_endpoint_requires_authentication():
    response = client.post("/jobs/ingest/greenhouse?board=stripe")
    assert response.status_code == 401


def test_ingest_endpoint_rejects_invalid_jobs():
    _clean_jobs()

    from app.connectors.greenhouse.greenhouse_connector import GreenhouseConnector

    invalid_jobs = [{"id": 123, "title": "", "content": "Bad job", "absolute_url": "https://example.com/job/123"}]
    original_fetch = GreenhouseConnector.fetch_jobs
    GreenhouseConnector.fetch_jobs = classmethod(lambda cls, board: invalid_jobs)  # type: ignore[assignment]
    try:
        response = client.post("/jobs/ingest/greenhouse?board=stripe", headers=_auth_headers())
        assert response.status_code == 400
    finally:
        GreenhouseConnector.fetch_jobs = original_fetch
        _clean_jobs()


def test_source_registry_supports_multiple_boards_and_disabled_configuration():
    from app.connectors.source_registry import source_registry

    source_registry.register_greenhouse_board("acme")
    source_registry.register_greenhouse_board("disabled", enabled=False)

    assert source_registry.resolve("greenhouse", "acme") is not None
    assert source_registry.resolve("greenhouse", "disabled") is None
    assert source_registry.resolve("unknown", "acme") is None


def test_ingestion_updates_changed_job_and_persists_run_summary():
    _clean_jobs()
    _clean_ingestion_runs()

    from app.connectors.greenhouse.greenhouse_connector import GreenhouseConnector
    from app.connectors.source_registry import source_registry

    source_registry.register_greenhouse_board("acme")
    payload = {
        "id": 8123001,
        "title": "Backend Engineer",
        "content": "Original description",
        "location": {"name": "Remote"},
        "absolute_url": "https://acme.example/jobs/8123001",
    }
    original_fetch = GreenhouseConnector.fetch_jobs
    GreenhouseConnector.fetch_jobs = classmethod(lambda cls, board: [payload])  # type: ignore[assignment]
    try:
        first = client.post("/jobs/ingest/greenhouse?board=acme", headers=_auth_headers())
        assert first.status_code == 200, first.text
        assert first.json()["created"] == 1

        GreenhouseConnector.fetch_jobs = classmethod(  # type: ignore[assignment]
            lambda cls, board: [{**payload, "content": "Updated description"}]
        )
        second = client.post("/jobs/ingest/greenhouse?board=acme", headers=_auth_headers())
        assert second.status_code == 200, second.text
        second_payload = second.json()
        assert second_payload["updated"] == 1
        assert second_payload["skipped_duplicates"] == 0
        assert second_payload["status"] == "completed"
        assert second_payload["source_identifier"] == "acme"

        db = SessionLocal()
        try:
            job = db.query(Job).filter(Job.source_job_id == "8123001").one()
            run = db.query(IngestionRun).filter(IngestionRun.id == second_payload["run_id"]).one()
            assert job.description == "Updated description"
            assert run.updated == 1
            assert run.status == "completed"
        finally:
            db.close()
    finally:
        GreenhouseConnector.fetch_jobs = original_fetch
        _clean_jobs()
        _clean_ingestion_runs()


def test_ingest_endpoint_rejects_unregistered_board():
    response = client.post("/jobs/ingest/greenhouse?board=not-registered", headers=_auth_headers())
    assert response.status_code == 400
