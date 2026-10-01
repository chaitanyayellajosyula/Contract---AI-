from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.core.database import SessionLocal
from app.main import app
from app.models.discovered_source import DiscoveredSource
from app.models.discovery_run import DiscoveryRun
from app.models.ingestion_run import IngestionRun
from app.models.user import User, UserRole
from app.services.auth_service import AuthService
from app.services.source_health_service import SourceHealthService

client = TestClient(app)
_NOW = datetime(2026, 10, 1, 12, tzinfo=timezone.utc)


def _clean_health_data() -> None:
    db = SessionLocal()
    try:
        db.query(IngestionRun).delete()
        db.query(DiscoveryRun).delete()
        db.query(DiscoveredSource).delete()
        db.commit()
    finally:
        db.close()


def _add_source(
    identifier: str,
    failures: int = 0,
    cooldown_started_at: datetime | None = None,
    success_at: datetime | None = None,
    error: str | None = None,
) -> None:
    timestamp = _NOW.replace(tzinfo=None)
    db = SessionLocal()
    try:
        db.add(DiscoveredSource(
            source="ashby",
            identifier=identifier,
            jobs_endpoint=f"https://api.ashbyhq.com/posting-api/job-board/{identifier}",
            status="validated",
            validation_status="valid",
            eligible=True,
            first_discovered_at=timestamp,
            last_checked_at=timestamp,
            last_validated_at=timestamp,
            consecutive_automatic_ingestion_failures=failures,
            automatic_ingestion_cooldown_started_at=cooldown_started_at,
            last_automatic_ingestion_success_at=success_at,
            last_automatic_ingestion_error=error,
        ))
        db.commit()
    finally:
        db.close()


def _add_ingestion_run(identifier: str, status: str, started_at: datetime, message: str | None = None) -> None:
    db = SessionLocal()
    try:
        db.add(IngestionRun(
            source="ashby",
            source_identifier=identifier,
            started_at=started_at.replace(tzinfo=None),
            completed_at=started_at.replace(tzinfo=None),
            status=status,
            message=message,
        ))
        db.commit()
    finally:
        db.close()


def _auth_headers(role: str, email: str) -> dict[str, str]:
    db = SessionLocal()
    try:
        user = User(
            full_name="Health Test User",
            email=email,
            hashed_password="unused-test-hash",
            role=role,
            is_active=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        token = AuthService(db).create_access_token(user)
        return {"Authorization": f"Bearer {token}"}
    finally:
        db.close()


def test_health_summary_is_empty_without_discovered_sources():
    _clean_health_data()
    db = SessionLocal()
    try:
        result = SourceHealthService(db, clock=lambda: _NOW).summarize()
        assert result["summary"]["total_discovered_sources"] == 0
        assert result["summary"]["healthy_sources"] == 0
        assert result["summary"]["unhealthy_sources"] == 0
        assert result["summary"]["sources_in_cooldown"] == 0
        assert result["summary"]["sources_eligible_for_recovery"] == 0
        assert result["sources"] == []
        assert result["recent_runs"] == []
    finally:
        db.close()


def test_health_summary_classifies_sources_and_aggregates_recent_audit_data():
    _clean_health_data()
    _add_source("healthy", success_at=_NOW - timedelta(hours=3))
    _add_source("cooling", failures=3, cooldown_started_at=_NOW - timedelta(minutes=30), error="token=secret-value")
    _add_source("recovery", failures=4, cooldown_started_at=_NOW - timedelta(hours=2), error="down")
    _add_source("recovered", success_at=_NOW - timedelta(minutes=5))
    _add_source("never-successful", failures=1, error="timeout")
    _add_ingestion_run("healthy", "completed", _NOW - timedelta(hours=3))
    _add_ingestion_run("cooling", "failed", _NOW - timedelta(minutes=20), "Authorization: Bearer audit-secret")
    _add_ingestion_run("recovery", "failed", _NOW - timedelta(hours=3))
    _add_ingestion_run("recovered", "completed", _NOW - timedelta(minutes=5))
    _add_ingestion_run("never-successful", "failed", _NOW - timedelta(days=8))

    db = SessionLocal()
    try:
        db.add(DiscoveryRun(
            run_type="automatic_ingestion",
            started_at=_NOW.replace(tzinfo=None),
            completed_at=_NOW.replace(tzinfo=None),
            status="completed",
            automatic_ingestion_health_results=[
                {
                    "source": "ashby",
                    "source_identifier": "recovered",
                    "event": "recovered",
                    "health_state": "healthy",
                    "timestamp": _NOW.isoformat(),
                    "exception": "must not be exposed",
                }
            ],
        ))
        db.commit()
        result = SourceHealthService(db, clock=lambda: _NOW).summarize()
    finally:
        db.close()

    summary = result["summary"]
    assert summary["total_discovered_sources"] == 5
    assert summary["healthy_sources"] == 3
    assert summary["unhealthy_sources"] == 2
    assert summary["sources_in_cooldown"] == 1
    assert summary["sources_eligible_for_recovery"] == 1
    assert summary["sources_never_successfully_ingested"] == 3
    assert summary["total_ingestion_failures"] == 3
    assert summary["recent_ingestion_failures"] == 2
    assert summary["most_recent_successful_ingestion"].startswith("2026-10-01T11:55:00")
    assert summary["most_recent_failure"].startswith("2026-10-01T11:40:00")

    by_identifier = {source["identifier"]: source for source in result["sources"]}
    assert by_identifier["healthy"]["health_state"] == "healthy"
    assert by_identifier["cooling"]["health_state"] == "cooldown"
    assert by_identifier["cooling"]["in_cooldown"] is True
    assert by_identifier["cooling"]["consecutive_failures"] == 3
    assert "secret-value" not in by_identifier["cooling"]["last_error"]
    assert "audit-secret" not in str(result)
    assert by_identifier["recovery"]["health_state"] == "recovery_eligible"
    assert by_identifier["recovery"]["eligible_for_recovery"] is True
    assert by_identifier["recovered"]["health_state"] == "healthy"
    assert by_identifier["recovered"]["recent_health_events"][0]["event"] == "recovered"
    assert by_identifier["never-successful"]["never_successfully_ingested"] is True
    assert "exception" not in str(result)
    assert result["recent_runs"][0]["run_type"] == "automatic_ingestion"
    _clean_health_data()


def test_source_health_endpoint_requires_auth_and_admin_role():
    _clean_health_data()
    unauthenticated = client.get("/admin/source-health")
    assert unauthenticated.status_code == 401

    recruiter_email = "source-health-recruiter@example.test"
    admin_email = "source-health-admin@example.test"
    recruiter_headers = _auth_headers(UserRole.RECRUITER.value, recruiter_email)
    admin_headers = _auth_headers(UserRole.LEGACY_ADMIN.value, admin_email)
    try:
        assert client.get("/admin/source-health", headers=recruiter_headers).status_code == 403
        response = client.get("/admin/source-health", headers=admin_headers)
        assert response.status_code == 200
        payload = response.json()
        assert "summary" in payload
        assert "sources" in payload
        assert "recent_runs" in payload
        assert payload["summary"]["total_discovered_sources"] == 0
    finally:
        db = SessionLocal()
        try:
            db.query(User).filter(User.email.in_((recruiter_email, admin_email))).delete(synchronize_session=False)
            db.commit()
        finally:
            db.close()