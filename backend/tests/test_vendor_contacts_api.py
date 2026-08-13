import pytest
from fastapi.testclient import TestClient

from app.core.database import SessionLocal
from app.main import app
from app.models.company import Company
from app.models.user import User, UserRole
from app.models.vendor import Vendor
from app.models.vendor_contact import VendorContact
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


def _create_vendor(name: str, company: Company) -> Vendor:
    db = SessionLocal()
    try:
        vendor = Vendor(
            name=name,
            email=f"{name.lower().replace(' ', '')}@example.com",
            company_id=company.id,
        )
        db.add(vendor)
        db.commit()
        db.refresh(vendor)
        return vendor
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
        db.query(VendorContact).delete()
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


def test_recruiter_can_create_vendor_contact():
    company_a = _create_company("Company A")
    recruiter = _create_user("recruiter@example.com", "Recruiter", company_a)
    vendor = _create_vendor("Vendor A", company_a)
    headers = _auth_headers_for("recruiter@example.com")

    response = client.post(
        f"/vendor-contacts/{vendor.id}",
        json={
            "full_name": "Ada Lovelace",
            "email": "ada@example.com",
            "designation": "Recruiter",
        },
        headers=headers,
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["vendor_id"] == vendor.id
    assert payload["full_name"] == "Ada Lovelace"


def test_recruiter_cannot_create_contact_for_different_company_vendor():
    company_a = _create_company("Company A")
    company_b = _create_company("Company B")
    recruiter_a = _create_user("recruiter_a@example.com", "Recruiter A", company_a)
    vendor_b = _create_vendor("Vendor B", company_b)
    headers = _auth_headers_for("recruiter_a@example.com")

    response = client.post(
        f"/vendor-contacts/{vendor_b.id}",
        json={
            "full_name": "Grace Hopper",
            "email": "grace@example.com",
        },
        headers=headers,
    )

    assert response.status_code == 404


def test_recruiter_can_list_own_company_vendor_contacts():
    company_a = _create_company("Company A")
    recruiter = _create_user("recruiter@example.com", "Recruiter", company_a)
    vendor_a = _create_vendor("Vendor A", company_a)

    db = SessionLocal()
    try:
        contact1 = VendorContact(
            vendor_id=vendor_a.id,
            full_name="Ada",
            email="ada@example.com",
        )
        contact2 = VendorContact(
            vendor_id=vendor_a.id,
            full_name="Grace",
            email="grace@example.com",
        )
        db.add_all([contact1, contact2])
        db.commit()
    finally:
        db.close()

    headers = _auth_headers_for("recruiter@example.com")
    response = client.get("/vendor-contacts", headers=headers)

    assert response.status_code == 200
    contacts = response.json()
    assert len(contacts) == 2


def test_recruiter_cannot_see_different_company_contacts():
    company_a = _create_company("Company A")
    company_b = _create_company("Company B")
    recruiter_a = _create_user("recruiter_a@example.com", "Recruiter A", company_a)
    recruiter_b = _create_user("recruiter_b@example.com", "Recruiter B", company_b)
    vendor_b = _create_vendor("Vendor B", company_b)

    db = SessionLocal()
    try:
        contact = VendorContact(
            vendor_id=vendor_b.id,
            full_name="Grace",
            email="grace@example.com",
        )
        db.add(contact)
        db.commit()
        db.refresh(contact)
        contact_id = contact.id
    finally:
        db.close()

    headers_a = _auth_headers_for("recruiter_a@example.com")
    response = client.get(f"/vendor-contacts/{contact_id}", headers=headers_a)

    assert response.status_code == 404


def test_recruiter_can_update_own_vendor_contact():
    company_a = _create_company("Company A")
    recruiter = _create_user("recruiter@example.com", "Recruiter", company_a)
    vendor_a = _create_vendor("Vendor A", company_a)

    db = SessionLocal()
    try:
        contact = VendorContact(
            vendor_id=vendor_a.id,
            full_name="Ada",
            email="ada@example.com",
        )
        db.add(contact)
        db.commit()
        db.refresh(contact)
        contact_id = contact.id
    finally:
        db.close()

    headers = _auth_headers_for("recruiter@example.com")
    response = client.patch(
        f"/vendor-contacts/{contact_id}",
        json={"full_name": "Ada Byron"},
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json()["full_name"] == "Ada Byron"


def test_recruiter_can_delete_own_vendor_contact():
    company_a = _create_company("Company A")
    recruiter = _create_user("recruiter@example.com", "Recruiter", company_a)
    vendor_a = _create_vendor("Vendor A", company_a)

    db = SessionLocal()
    try:
        contact = VendorContact(
            vendor_id=vendor_a.id,
            full_name="Ada",
            email="ada@example.com",
        )
        db.add(contact)
        db.commit()
        db.refresh(contact)
        contact_id = contact.id
    finally:
        db.close()

    headers = _auth_headers_for("recruiter@example.com")
    response = client.delete(f"/vendor-contacts/{contact_id}", headers=headers)

    assert response.status_code == 204


def test_duplicate_email_returns_409():
    company_a = _create_company("Company A")
    recruiter = _create_user("recruiter@example.com", "Recruiter", company_a)
    vendor_a = _create_vendor("Vendor A", company_a)
    headers = _auth_headers_for("recruiter@example.com")

    # First contact
    response1 = client.post(
        f"/vendor-contacts/{vendor_a.id}",
        json={
            "full_name": "Grace",
            "email": "grace@example.com",
        },
        headers=headers,
    )
    assert response1.status_code == 201

    # Duplicate email
    response2 = client.post(
        f"/vendor-contacts/{vendor_a.id}",
        json={
            "full_name": "Another Grace",
            "email": "grace@example.com",
        },
        headers=headers,
    )
    assert response2.status_code == 409


def test_non_manager_role_cannot_access_company_scoped_contacts():
    company_a = _create_company("Company A")
    member = _create_user("member@example.com", "Member", company_a, role=UserRole.LEGACY_MEMBER.value)
    vendor_a = _create_vendor("Vendor A", company_a)

    db = SessionLocal()
    try:
        contact = VendorContact(
            vendor_id=vendor_a.id,
            full_name="Ada",
            email="ada@example.com",
        )
        db.add(contact)
        db.commit()
        db.refresh(contact)
        contact_id = contact.id
    finally:
        db.close()

    headers = _auth_headers_for("member@example.com")
    get_response = client.get(f"/vendor-contacts/{contact_id}", headers=headers)
    assert get_response.status_code == 404

    create_response = client.post(
        f"/vendor-contacts/{vendor_a.id}",
        json={"full_name": "Grace", "email": "grace@example.com"},
        headers=headers,
    )
    assert create_response.status_code == 403

