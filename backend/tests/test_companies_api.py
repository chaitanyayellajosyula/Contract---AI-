from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_create_get_list_update_delete_companies():
    create_response = client.post(
        "/companies",
        json={
            "name": "Acme Corporation",
            "website": "https://acme.example",
            "industry": "Software",
            "location": "Remote",
        },
    )
    assert create_response.status_code == 201
    payload = create_response.json()
    company_id = payload["id"]

    get_response = client.get(f"/companies/{company_id}")
    assert get_response.status_code == 200
    assert get_response.json()["name"] == "Acme Corporation"

    list_response = client.get("/companies?industry=Software&location=Remote")
    assert list_response.status_code == 200
    assert len(list_response.json()) >= 1

    update_response = client.patch(
        f"/companies/{company_id}",
        json={"name": "Acme Labs", "industry": "Cloud"},
    )
    assert update_response.status_code == 200
    assert update_response.json()["name"] == "Acme Labs"
    assert update_response.json()["industry"] == "Cloud"

    delete_response = client.delete(f"/companies/{company_id}")
    assert delete_response.status_code == 204


def test_company_not_found():
    response = client.get("/companies/999999")
    assert response.status_code == 404
