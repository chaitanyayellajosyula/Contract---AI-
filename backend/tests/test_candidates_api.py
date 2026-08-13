from fastapi.testclient import TestClient

from app.core.auth import get_current_user
from app.core.database import SessionLocal
from app.main import app
from app.models.candidate import Candidate
from app.models.company import Company
from app.models.user import User, UserRole
from app.services.auth_service import AuthService

client = TestClient(app)


def _create_user(email: str, full_name: str = "Recruiter", company: Company | None = None) -> User:
    db = SessionLocal()
    try:
        existing = db.query(User).filter(User.email == email).first()
        if existing is not None:
            # If user exists but company_id doesn't match, update it
            if company and existing.company_id != company.id:
                existing.company_id = company.id
                db.commit()
                db.refresh(existing)
            return existing

        user = User(
            full_name=full_name,
            email=email,
            hashed_password=AuthService(db).hash_password("Password123!"),
            role=UserRole.RECRUITER.value,
            company_id=company.id if company else None,
            is_active=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user
    finally:
        db.close()


def _auth_headers_for(email: str) -> dict[str, str]:
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        if user is None:
            raise RuntimeError(f"User {email} not found")
        token = AuthService(db).create_access_token(user)
        return {"Authorization": f"Bearer {token}"}
    finally:
        db.close()


def _create_company(name: str) -> Company:
    db = SessionLocal()
    try:
        company = Company(name=name, website=f"https://{name.lower().replace(' ', '')}.example")
        db.add(company)
        db.commit()
        db.refresh(company)
        return company
    finally:
        db.close()


def setup_function():
    db = SessionLocal()
    try:
        db.query(Candidate).delete()
        db.query(Company).delete()
        db.query(User).filter(User.email.like("%example.com")).delete()
        db.commit()
    finally:
        db.close()


def test_create_candidate_and_ownership():
    company = _create_company("Acme")
    user = _create_user("rahul@example.com", "Rahul", company)
    headers = _auth_headers_for("rahul@example.com")

    response = client.post(
        "/candidates",
        json={
            "first_name": "Ava",
            "last_name": "Stone",
            "email": "ava@example.com",
            "phone": "555-0100",
            "current_location": "Austin, TX",
        },
        headers=headers,
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["owner_user_id"] == user.id
    assert payload["company_id"] == company.id
    assert payload["email"] == "ava@example.com"

    response = client.post(
        "/candidates",
        json={
            "owner_user_id": 99999,
            "first_name": "Mallory",
            "last_name": "Jones",
            "email": "mallory@example.com",
        },
        headers=headers,
    )
    assert response.status_code == 201
    assert response.json()["owner_user_id"] == user.id
    assert response.json()["company_id"] == company.id


def test_list_candidates_and_privacy_between_recruiters():
    company = _create_company("Beta")
    recruiter_a = _create_user("rahul2@example.com", "Rahul", company)
    recruiter_b = _create_user("priya@example.com", "Priya", company)

    db = SessionLocal()
    try:
        candidate_a = Candidate(
            owner_user_id=recruiter_a.id,
            company_id=company.id,
            first_name="One",
            last_name="Alpha",
            email="one@example.com",
        )
        candidate_b = Candidate(
            owner_user_id=recruiter_b.id,
            company_id=company.id,
            first_name="Two",
            last_name="Beta",
            email="two@example.com",
        )
        db.add_all([candidate_a, candidate_b])
        db.commit()
    finally:
        db.close()

    a_headers = _auth_headers_for("rahul2@example.com")
    b_headers = _auth_headers_for("priya@example.com")

    a_list = client.get("/candidates", headers=a_headers)
    b_list = client.get("/candidates", headers=b_headers)

    assert a_list.status_code == 200
    assert b_list.status_code == 200
    assert len(a_list.json()) == 1
    assert len(b_list.json()) == 1
    assert a_list.json()[0]["email"] == "one@example.com"
    assert b_list.json()[0]["email"] == "two@example.com"

    a_visible_ids = {item["id"] for item in a_list.json()}
    b_visible_ids = {item["id"] for item in b_list.json()}
    assert a_visible_ids != b_visible_ids


def test_get_update_delete_candidate_owner_only():
    company = _create_company("Gamma")
    recruiter_a = _create_user("owner1@example.com", "Owner One", company)
    recruiter_b = _create_user("owner2@example.com", "Owner Two", company)

    db = SessionLocal()
    try:
        candidate = Candidate(
            owner_user_id=recruiter_a.id,
            company_id=company.id,
            first_name="Owner",
            last_name="Candidate",
            email="owner.candidate@example.com",
        )
        other_candidate = Candidate(
            owner_user_id=recruiter_b.id,
            company_id=company.id,
            first_name="Other",
            last_name="Candidate",
            email="other.candidate@example.com",
        )
        db.add_all([candidate, other_candidate])
        db.commit()
        db.refresh(candidate)
        db.refresh(other_candidate)
    finally:
        db.close()

    a_headers = _auth_headers_for("owner1@example.com")
    b_headers = _auth_headers_for("owner2@example.com")

    get_ok = client.get(f"/candidates/{candidate.id}", headers=a_headers)
    assert get_ok.status_code == 200
    assert get_ok.json()["email"] == "owner.candidate@example.com"

    get_forbidden = client.get(f"/candidates/{candidate.id}", headers=b_headers)
    assert get_forbidden.status_code == 404

    patch_ok = client.patch(
        f"/candidates/{candidate.id}",
        json={"last_name": "Updated", "availability_status": "Available"},
        headers=a_headers,
    )
    assert patch_ok.status_code == 200
    assert patch_ok.json()["last_name"] == "Updated"

    patch_forbidden = client.patch(
        f"/candidates/{candidate.id}",
        json={"company_id": 123, "owner_user_id": recruiter_b.id},
        headers=b_headers,
    )
    assert patch_forbidden.status_code == 404

    delete_ok = client.delete(f"/candidates/{candidate.id}", headers=a_headers)
    assert delete_ok.status_code == 204

    delete_forbidden = client.delete(f"/candidates/{other_candidate.id}", headers=a_headers)
    assert delete_forbidden.status_code == 404

    with SessionLocal() as db:
        assert db.get(Candidate, candidate.id) is None
        assert db.get(Candidate, other_candidate.id) is not None


def test_owner_cannot_be_changed_and_not_found_is_404():
    company = _create_company("Delta")
    recruiter = _create_user("owner3@example.com", "Owner Three", company)

    db = SessionLocal()
    try:
        candidate = Candidate(
            owner_user_id=recruiter.id,
            company_id=company.id,
            first_name="Xena",
            last_name="Quill",
            email="xena@example.com",
        )
        db.add(candidate)
        db.commit()
        db.refresh(candidate)
    finally:
        db.close()

    headers = _auth_headers_for("owner3@example.com")

    response = client.patch(
        f"/candidates/{candidate.id}",
        json={"owner_user_id": 12345},
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json()["owner_user_id"] == recruiter.id

    missing = client.get("/candidates/999999", headers=headers)
    assert missing.status_code == 404

    delete_missing = client.delete("/candidates/999999", headers=headers)
    assert delete_missing.status_code == 404
