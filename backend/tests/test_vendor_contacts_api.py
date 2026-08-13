import pytest
from fastapi.testclient import TestClient

from app.core.database import SessionLocal
from app.main import app
from app.models.vendor_contact import VendorContact

client = TestClient(app)


@pytest.fixture(autouse=True)
def isolate_vendor_contact_state():
    db = SessionLocal()
    try:
        db.query(VendorContact).delete()
        db.commit()
    finally:
        db.close()

    yield

    db = SessionLocal()
    try:
        db.query(VendorContact).delete()
        db.commit()
    finally:
        db.close()


def test_create_get_list_update_delete_vendor_contacts():
    create_response = client.post(
        "/vendor-contacts",
        json={
            "vendor_id": 1,
            "full_name": "Ada Lovelace",
            "email": "ada@example.com",
            "phone": "555-0100",
            "designation": "Recruiter",
            "is_active": True,
        },
    )
    assert create_response.status_code == 201
    payload = create_response.json()
    contact_id = payload["id"]

    get_response = client.get(f"/vendor-contacts/{contact_id}")
    assert get_response.status_code == 200
    assert get_response.json()["email"] == "ada@example.com"

    list_response = client.get("/vendor-contacts?designation=Recruiter&is_active=true")
    assert list_response.status_code == 200
    assert len(list_response.json()) >= 1

    update_response = client.patch(
        f"/vendor-contacts/{contact_id}",
        json={"full_name": "Ada Byron", "is_active": False},
    )
    assert update_response.status_code == 200
    assert update_response.json()["full_name"] == "Ada Byron"
    assert update_response.json()["is_active"] is False

    delete_response = client.delete(f"/vendor-contacts/{contact_id}")
    assert delete_response.status_code == 204


def test_duplicate_email_and_not_found():
    first_response = client.post(
        "/vendor-contacts",
        json={
            "vendor_id": 1,
            "full_name": "Grace Hopper",
            "email": "grace@example.com",
            "designation": "Manager",
        },
    )
    assert first_response.status_code == 201

    duplicate_response = client.post(
        "/vendor-contacts",
        json={
            "vendor_id": 1,
            "full_name": "Another Grace",
            "email": "grace@example.com",
            "designation": "Manager",
        },
    )
    assert duplicate_response.status_code == 409

    not_found_response = client.get("/vendor-contacts/999999")
    assert not_found_response.status_code == 404
