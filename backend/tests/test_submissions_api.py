from fastapi.testclient import TestClient

from app.core.database import SessionLocal
from app.main import app
from app.models import Candidate, Company, Job, Submission, User
from app.models.user import UserRole
from app.services.auth_service import AuthService


client = TestClient(app)


def _company(name: str) -> Company:
    db = SessionLocal()
    try:
        company = Company(name=name)
        db.add(company)
        db.commit()
        db.refresh(company)
        return company
    finally:
        db.close()


def _user(email: str, company: Company, role: str = UserRole.RECRUITER.value) -> User:
    db = SessionLocal()
    try:
        user = User(
            full_name=email.split("@")[0],
            email=email,
            hashed_password=AuthService(db).hash_password("Password123!"),
            role=role,
            company_id=company.id,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user
    finally:
        db.close()


def _headers(user: User) -> dict[str, str]:
    db = SessionLocal()
    try:
        return {"Authorization": f"Bearer {AuthService(db).create_access_token(user)}"}
    finally:
        db.close()


def _candidate(owner: User, company: Company, email: str) -> Candidate:
    db = SessionLocal()
    try:
        candidate = Candidate(
            owner_user_id=owner.id,
            company_id=company.id,
            first_name="Ada",
            last_name="Lovelace",
            email=email,
        )
        db.add(candidate)
        db.commit()
        db.refresh(candidate)
        return candidate
    finally:
        db.close()


def _job(company: Company, title: str) -> Job:
    db = SessionLocal()
    try:
        job = Job(title=title, company_id=company.id, source="manual")
        db.add(job)
        db.commit()
        db.refresh(job)
        return job
    finally:
        db.close()


def _cleanup() -> None:
    db = SessionLocal()
    try:
        db.query(Submission).delete()
        db.query(Candidate).delete()
        db.query(Job).delete()
        db.query(User).filter(User.email.like("submission-%@example.com")).delete()
        db.query(Company).filter(Company.name.like("Submission %")).delete()
        db.commit()
    finally:
        db.close()


def setup_function() -> None:
    _cleanup()


def teardown_function() -> None:
    _cleanup()


def test_recruiter_can_create_update_and_delete_submission() -> None:
    company = _company("Submission Acme")
    recruiter = _user("submission-recruiter@example.com", company)
    candidate = _candidate(recruiter, company, "submission-candidate@example.com")
    job = _job(company, "Python Engineer")
    headers = _headers(recruiter)

    response = client.post("/submissions", json={"candidate_id": candidate.id, "job_id": job.id, "notes": "Strong fit"}, headers=headers)
    assert response.status_code == 201
    submission_id = response.json()["id"]
    assert response.json()["status"] == "SUBMITTED"

    response = client.patch(f"/submissions/{submission_id}", json={"status": "REVIEWING"}, headers=headers)
    assert response.status_code == 200
    assert response.json()["status"] == "REVIEWING"

    assert client.delete(f"/submissions/{submission_id}", headers=headers).status_code == 204


def test_duplicate_submission_is_rejected() -> None:
    company = _company("Submission Duplicate")
    recruiter = _user("submission-duplicate@example.com", company)
    candidate = _candidate(recruiter, company, "submission-duplicate-candidate@example.com")
    job = _job(company, "Backend Engineer")
    headers = _headers(recruiter)
    payload = {"candidate_id": candidate.id, "job_id": job.id}

    assert client.post("/submissions", json=payload, headers=headers).status_code == 201
    response = client.post("/submissions", json=payload, headers=headers)
    assert response.status_code == 409


def test_recruiter_and_company_admin_boundaries_are_enforced() -> None:
    company_a = _company("Submission Company A")
    company_b = _company("Submission Company B")
    recruiter_a = _user("submission-owner@example.com", company_a)
    recruiter_b = _user("submission-other@example.com", company_a)
    admin_b = _user("submission-admin@example.com", company_b, UserRole.COMPANY_ADMIN.value)
    candidate = _candidate(recruiter_a, company_a, "submission-boundary@example.com")
    job = _job(company_a, "Platform Engineer")
    submission_response = client.post("/submissions", json={"candidate_id": candidate.id, "job_id": job.id}, headers=_headers(recruiter_a))
    submission_id = submission_response.json()["id"]

    assert client.get(f"/submissions/{submission_id}", headers=_headers(recruiter_b)).status_code == 404
    assert client.get(f"/submissions/{submission_id}", headers=_headers(admin_b)).status_code == 404
    assert client.get("/submissions", headers=_headers(recruiter_a)).json()[0]["id"] == submission_id