from datetime import datetime, timedelta

from fastapi.testclient import TestClient

from app.core.database import SessionLocal
from app.main import app
from app.models.job import Job
from app.models.job_user_status import JobUserStatus
from app.models.user import User
from app.services.auth_service import AuthService

client = TestClient(app)


def _user(email: str) -> dict[str, str]:
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        if user is None:
            user = User(
                full_name=email.split("@")[0],
                email=email,
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
        db.query(JobUserStatus).delete()
        db.query(Job).delete()
        db.commit()
    finally:
        db.close()


def _create_job(title: str, **fields) -> int:
    payload = {
        "title": title,
        "source": "ashby",
        "source_job_id": title.lower().replace(" ", "-"),
        "source_company": fields.pop("source_company", "Acme Staffing"),
        "posted_at": fields.pop("posted_at", datetime.utcnow().isoformat()),
        "remote_type": fields.pop("remote_type", "remote"),
        "employment_type": fields.pop("employment_type", "contract"),
        **fields,
    }
    response = client.post("/jobs", json=payload)
    assert response.status_code == 201, response.text
    return response.json()["id"]


def test_job_listing_filters_paginates_and_sorts_by_freshness():
    _clean()
    _create_job("Recent Contract", posted_at=(datetime.utcnow() - timedelta(days=6)).isoformat(), location="Austin")
    newest_id = _create_job("Newest Contract", posted_at=datetime.utcnow().isoformat(), location="Remote US")
    _create_job("Full Time Role", employment_type="full_time", posted_at=datetime.utcnow().isoformat(), location="Boston")

    response = client.get("/jobs?engagement=contract&freshness=last_7_days&page=1&page_size=1")

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["id"] == newest_id
    assert response.headers["X-Total-Count"] == "2"
    assert response.headers["X-Page"] == "1"


def test_job_listing_supports_keyword_location_source_and_company_filters():
    _clean()
    target_id = _create_job("Platform Contract Engineer", location="Chicago", source_company="Northstar Tech")
    _create_job("Other Role", location="Remote", source_company="Other Co")

    response = client.get("/jobs?title=Platform&location=Chicago&source=ashby&company=Northstar")

    assert [job["id"] for job in response.json()] == [target_id]


def test_job_status_is_authenticated_and_isolated_per_user():
    _clean()
    job_id = _create_job("Status Workflow Job")
    user_one = _user("workflow-one@example.com")
    user_two = _user("workflow-two@example.com")

    unauthorized = client.patch(f"/jobs/{job_id}/status", json={"saved": True})
    assert unauthorized.status_code == 401

    saved = client.patch(f"/jobs/{job_id}/status", json={"viewed": True, "saved": True}, headers=user_one)
    assert saved.status_code == 200
    assert saved.json()["viewed"] is True
    assert saved.json()["saved"] is True
    assert saved.json()["hidden"] is False

    user_one_list = client.get("/jobs?saved=true", headers=user_one)
    user_two_list = client.get("/jobs?saved=true", headers=user_two)
    assert any(job["id"] == job_id for job in user_one_list.json())
    assert all(job["id"] != job_id for job in user_two_list.json())

    hidden = client.patch(f"/jobs/{job_id}/status", json={"hidden": True}, headers=user_one)
    assert hidden.status_code == 200
    hidden_list = client.get("/jobs?hidden=true", headers=user_one)
    visible_list = client.get("/jobs?hidden=false", headers=user_one)
    assert any(job["id"] == job_id for job in hidden_list.json())
    assert all(job["id"] != job_id for job in visible_list.json())
