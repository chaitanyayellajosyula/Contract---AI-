import pytest
from fastapi.testclient import TestClient

from app.core.database import SessionLocal
from app.main import app
from app.models.company import Company
from app.models.user import User, UserRole
from app.models.vendor import Vendor
from app.services.auth_service import AuthService

client = TestClient(app)


def _create_company(name: str) -> Company:
    db = SessionLocal()
    try:
        company = Company(name=name, website=f"https://{name.lower().replace(' ', '')}.example.com")
        db.add(company)
        db.commit()
        db.refresh(company)
        return company
    finally:
        db.close()


def _create_user(email: str, full_name: str, company: Company, role: str = UserRole.RECRUITER.value) -> User:
    db = SessionLocal()
    try:
        existing = db.query(User).filter(User.email == email).first()
        if existing is not None:
            return existing

        user = User(
            full_name=full_name,
            email=email,
            hashed_password=AuthService(db).hash_password("Password123!"),
            role=role,
            company_id=company.id,
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


def _cleanup():
    db = SessionLocal()
    try:
        db.query(Vendor).delete()
        db.query(User).filter(User.email.like("%@example.com")).delete()
        db.query(Company).delete()
        db.commit()
    finally:
        db.close()


@pytest.fixture(autouse=True)
def setup_teardown():
    _cleanup()
    yield
    _cleanup()


def test_recruiter_can_create_vendor():
    company_a = _create_company("Company A")
    recruiter = _create_user("recruiter@example.com", "Recruiter", company_a)
    headers = _auth_headers_for("recruiter@example.com")

    response = client.post(
        "/vendors",
        json={
            "name": "Tech Vendor",
            "email": "vendor@example.com",
            "phone": "555-0100",
        },
        headers=headers,
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["name"] == "Tech Vendor"
    assert payload["company_id"] == company_a.id


def test_recruiter_can_list_own_company_vendors():
    company_a = _create_company("Company A")
    recruiter = _create_user("recruiter@example.com", "Recruiter", company_a)

    db = SessionLocal()
    try:
        vendor1 = Vendor(name="Vendor A", email="vendor_a@example.com", company_id=company_a.id)
        vendor2 = Vendor(name="Vendor B", email="vendor_b@example.com", company_id=company_a.id)
        db.add_all([vendor1, vendor2])
        db.commit()
    finally:
        db.close()

    headers = _auth_headers_for("recruiter@example.com")
    response = client.get("/vendors", headers=headers)

    assert response.status_code == 200
    vendors = response.json()
    assert len(vendors) == 2
    assert all(v["company_id"] == company_a.id for v in vendors)


def test_recruiter_cannot_see_different_company_vendors():
    company_a = _create_company("Company A")
    company_b = _create_company("Company B")
    recruiter_a = _create_user("recruiter_a@example.com", "Recruiter A", company_a)

    db = SessionLocal()
    try:
        vendor_b = Vendor(name="Vendor B", email="vendor_b@example.com", company_id=company_b.id)
        db.add(vendor_b)
        db.commit()
        db.refresh(vendor_b)
        vendor_id = vendor_b.id
    finally:
        db.close()

    headers_a = _auth_headers_for("recruiter_a@example.com")
    response = client.get(f"/vendors/{vendor_id}", headers=headers_a)

    assert response.status_code == 404


def test_recruiter_can_get_own_company_vendor():
    company_a = _create_company("Company A")
    recruiter = _create_user("recruiter@example.com", "Recruiter", company_a)

    db = SessionLocal()
    try:
        vendor = Vendor(name="Vendor A", email="vendor_a@example.com", company_id=company_a.id)
        db.add(vendor)
        db.commit()
        db.refresh(vendor)
        vendor_id = vendor.id
    finally:
        db.close()

    headers = _auth_headers_for("recruiter@example.com")
    response = client.get(f"/vendors/{vendor_id}", headers=headers)

    assert response.status_code == 200
    assert response.json()["name"] == "Vendor A"


def test_recruiter_can_update_vendor():
    company_a = _create_company("Company A")
    recruiter = _create_user("recruiter@example.com", "Recruiter", company_a)

    db = SessionLocal()
    try:
        vendor = Vendor(name="Vendor A", email="vendor_a@example.com", company_id=company_a.id)
        db.add(vendor)
        db.commit()
        db.refresh(vendor)
        vendor_id = vendor.id
    finally:
        db.close()

    headers = _auth_headers_for("recruiter@example.com")
    response = client.patch(
        f"/vendors/{vendor_id}",
        json={"name": "Updated Vendor"},
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json()["name"] == "Updated Vendor"


def test_recruiter_cannot_override_company_id():
    company_a = _create_company("Company A")
    company_b = _create_company("Company B")
    recruiter = _create_user("recruiter@example.com", "Recruiter", company_a)

    db = SessionLocal()
    try:
        vendor = Vendor(name="Vendor A", email="vendor_a@example.com", company_id=company_a.id)
        db.add(vendor)
        db.commit()
        db.refresh(vendor)
        vendor_id = vendor.id
    finally:
        db.close()

    headers = _auth_headers_for("recruiter@example.com")
    response = client.patch(
        f"/vendors/{vendor_id}",
        json={"company_id": company_b.id},
        headers=headers,
    )

    assert response.status_code == 200
    # company_id should remain unchanged
    assert response.json()["company_id"] == company_a.id


def test_recruiter_can_delete_vendor():
    company_a = _create_company("Company A")
    recruiter = _create_user("recruiter@example.com", "Recruiter", company_a)

    db = SessionLocal()
    try:
        vendor = Vendor(name="Vendor A", email="vendor_a@example.com", company_id=company_a.id)
        db.add(vendor)
        db.commit()
        db.refresh(vendor)
        vendor_id = vendor.id
    finally:
        db.close()

    headers = _auth_headers_for("recruiter@example.com")
    response = client.delete(f"/vendors/{vendor_id}", headers=headers)

    assert response.status_code == 204


def test_recruiter_cannot_delete_different_company_vendor():
    company_a = _create_company("Company A")
    company_b = _create_company("Company B")
    recruiter_a = _create_user("recruiter_a@example.com", "Recruiter A", company_a)

    db = SessionLocal()
    try:
        vendor_b = Vendor(name="Vendor B", email="vendor_b@example.com", company_id=company_b.id)
        db.add(vendor_b)
        db.commit()
        db.refresh(vendor_b)
        vendor_id = vendor_b.id
    finally:
        db.close()

    headers_a = _auth_headers_for("recruiter_a@example.com")
    response = client.delete(f"/vendors/{vendor_id}", headers=headers_a)

    assert response.status_code == 404


def test_non_manager_role_cannot_access_company_scoped_vendors():
    company_a = _create_company("Company A")
    member = _create_user("member@example.com", "Member", company_a, role=UserRole.LEGACY_MEMBER.value)

    db = SessionLocal()
    try:
        vendor = Vendor(name="Vendor A", email="vendor_a@example.com", company_id=company_a.id)
        db.add(vendor)
        db.commit()
        db.refresh(vendor)
        vendor_id = vendor.id
    finally:
        db.close()

    headers = _auth_headers_for("member@example.com")
    get_response = client.get(f"/vendors/{vendor_id}", headers=headers)
    assert get_response.status_code == 404

    create_response = client.post(
        "/vendors",
        json={"name": "Blocked Vendor", "email": "blocked@example.com"},
        headers=headers,
    )
    assert create_response.status_code == 403
