from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_create_get_list_update_delete_jobs():
    create_response = client.post(
        "/jobs",
        json={
            "title": "Senior Python Engineer",
            "description": "Build resilient integrations",
            "location": "Remote",
            "employment_type": "full_time",
            "remote_type": "remote",
            "status": "active",
            "source": "manual",
            "source_job_id": "job-001",
        },
    )
    assert create_response.status_code == 201
    payload = create_response.json()
    job_id = payload["id"]

    get_response = client.get(f"/jobs/{job_id}")
    assert get_response.status_code == 200
    assert get_response.json()["title"] == "Senior Python Engineer"

    list_response = client.get("/jobs?location=Remote&status=active")
    assert list_response.status_code == 200
    assert len(list_response.json()) >= 1

    update_response = client.patch(
        f"/jobs/{job_id}",
        json={"title": "Principal Python Engineer", "status": "review"},
    )
    assert update_response.status_code == 200
    assert update_response.json()["title"] == "Principal Python Engineer"
    assert update_response.json()["status"] == "review"

    delete_response = client.delete(f"/jobs/{job_id}")
    assert delete_response.status_code == 204


def test_job_not_found():
    response = client.get("/jobs/999999")
    assert response.status_code == 404
