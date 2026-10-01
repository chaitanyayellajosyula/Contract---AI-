from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import or_

from app.core.database import SessionLocal
from app.main import app
from app.models.candidate import Candidate
from app.models.company import Company
from app.models.job import Job
from app.models.recruiter import Recruiter
from app.models.submission import Submission, SubmissionStatusHistory
from app.models.user import User, UserRole
from app.models.vendor import Vendor
from app.models.vendor_contact import VendorContact
from app.services.auth_service import AuthService


client = TestClient(app)
_PREFIX = "sprint11-"


def _create_records():
    db = SessionLocal()
    try:
        company = Company(name="Sprint 11 Test Company", website="https://sprint11.example.test", location="Seattle, WA")
        foreign_company = Company(name="Sprint 11 Test Foreign", website="https://foreign.example.test")
        db.add_all([company, foreign_company])
        db.flush()
        recruiter = User(
            full_name="Sprint 11 Recruiter",
            email=f"{_PREFIX}recruiter@example.test",
            hashed_password="test-hash",
            role=UserRole.RECRUITER.value,
            company_id=company.id,
        )
        teammate = User(
            full_name="Sprint 11 Teammate",
            email=f"{_PREFIX}teammate@example.test",
            hashed_password="test-hash",
            role=UserRole.RECRUITER.value,
            company_id=company.id,
        )
        company_admin = User(
            full_name="Sprint 11 Company Admin",
            email=f"{_PREFIX}company-admin@example.test",
            hashed_password="test-hash",
            role=UserRole.COMPANY_ADMIN.value,
            company_id=company.id,
        )
        foreign_user = User(
            full_name="Sprint 11 Foreign Recruiter",
            email=f"{_PREFIX}foreign@example.test",
            hashed_password="test-hash",
            role=UserRole.RECRUITER.value,
            company_id=foreign_company.id,
        )
        global_admin = User(
            full_name="Sprint 11 Global Admin",
            email=f"{_PREFIX}admin@example.test",
            hashed_password="test-hash",
            role=UserRole.LEGACY_ADMIN.value,
        )
        db.add_all([recruiter, teammate, company_admin, foreign_user, global_admin])
        db.flush()
        candidate = Candidate(
            owner_user_id=recruiter.id,
            company_id=company.id,
            first_name="Casey",
            last_name="Rivera",
            email=f"{_PREFIX}candidate@example.test",
            current_location="Austin, TX",
            preferred_location="Seattle, WA",
            total_experience="8 years",
            visa_status="H1B",
            expected_rate="$100/hour",
            availability_status="Available",
        )
        teammate_candidate = Candidate(
            owner_user_id=teammate.id,
            company_id=company.id,
            first_name="Taylor",
            last_name="Quinn",
            email=f"{_PREFIX}teammate-candidate@example.test",
            current_location="Dallas, TX",
            availability_status="Interviewing",
        )
        foreign_candidate = Candidate(
            owner_user_id=foreign_user.id,
            company_id=foreign_company.id,
            first_name="Morgan",
            last_name="Lee",
            email=f"{_PREFIX}foreign-candidate@example.test",
        )
        vendor = Vendor(name="Sprint 11 Vendor Alpha", email="alpha@sprint11.example.test", company_id=company.id)
        empty_vendor = Vendor(name="Sprint 11 Vendor Empty", company_id=company.id)
        foreign_vendor = Vendor(name="Sprint 11 Vendor Foreign", company_id=foreign_company.id)
        db.add_all([candidate, teammate_candidate, foreign_candidate, vendor, empty_vendor, foreign_vendor])
        db.flush()
        vendor_recruiter = Recruiter(full_name="Vendor Account", vendor_id=vendor.id)
        foreign_vendor_recruiter = Recruiter(full_name="Foreign Account", vendor_id=foreign_vendor.id)
        db.add_all([vendor_recruiter, foreign_vendor_recruiter])
        db.flush()
        job = Job(
            title="Platform Engineer",
            location="Seattle, WA",
            employment_type="Contract",
            source="greenhouse",
            source_company=company.name,
            source_job_id=f"{_PREFIX}job-alpha",
            recruiter_id=vendor_recruiter.id,
            posted_at=datetime(2026, 10, 1),
            created_at=datetime(2026, 10, 1),
            updated_at=datetime(2026, 10, 1),
        )
        foreign_job = Job(
            title="Foreign Platform Engineer",
            company_id=foreign_company.id,
            source="lever",
            source_job_id=f"{_PREFIX}job-foreign",
            recruiter_id=foreign_vendor_recruiter.id,
        )
        db.add_all([job, foreign_job])
        db.flush()
        contacts = [
            VendorContact(vendor_id=vendor.id, full_name="Search Contact One", email=f"{_PREFIX}contact1@example.test"),
            VendorContact(vendor_id=vendor.id, full_name="Search Contact Two", email=f"{_PREFIX}contact2@example.test"),
        ]
        db.add_all(contacts)
        submission = Submission(
            candidate_id=candidate.id,
            job_id=job.id,
            company_id=company.id,
            submitted_by_user_id=recruiter.id,
            status="REVIEWING",
            created_at=datetime(2026, 9, 28),
            updated_at=datetime(2026, 10, 1),
        )
        teammate_submission = Submission(
            candidate_id=teammate_candidate.id,
            job_id=job.id,
            company_id=company.id,
            submitted_by_user_id=teammate.id,
            status="SUBMITTED",
        )
        db.add_all([submission, teammate_submission])
        db.commit()
        return {
            "company_id": company.id,
            "foreign_company_id": foreign_company.id,
            "recruiter_id": recruiter.id,
            "teammate_id": teammate.id,
            "company_admin_id": company_admin.id,
            "foreign_user_id": foreign_user.id,
            "global_admin_id": global_admin.id,
            "candidate_id": candidate.id,
            "teammate_candidate_id": teammate_candidate.id,
            "foreign_candidate_id": foreign_candidate.id,
            "vendor_id": vendor.id,
            "empty_vendor_id": empty_vendor.id,
            "foreign_vendor_id": foreign_vendor.id,
            "job_id": job.id,
            "submission_id": submission.id,
        }
    finally:
        db.close()


def _headers(user_id: int) -> dict[str, str]:
    db = SessionLocal()
    try:
        user = db.get(User, user_id)
        return {"Authorization": f"Bearer {AuthService(db).create_access_token(user)}"}
    finally:
        db.close()


@pytest.fixture
def records():
    data = _create_records()
    yield data
    db = SessionLocal()
    try:
        company_ids = [row[0] for row in db.query(Company.id).filter(Company.name.like("Sprint 11 Test %")).all()]
        candidate_ids = [row[0] for row in db.query(Candidate.id).filter(Candidate.email.like(f"{_PREFIX}%")).all()]
        vendor_ids = [row[0] for row in db.query(Vendor.id).filter(Vendor.company_id.in_(company_ids)).all()] if company_ids else []
        recruiter_ids = [row[0] for row in db.query(Recruiter.id).filter(Recruiter.vendor_id.in_(vendor_ids)).all()] if vendor_ids else []
        job_ids = [row[0] for row in db.query(Job.id).filter(or_(Job.company_id.in_(company_ids), Job.recruiter_id.in_(recruiter_ids))).all()] if company_ids else []
        submission_ids = [row[0] for row in db.query(Submission.id).filter(or_(Submission.candidate_id.in_(candidate_ids), Submission.job_id.in_(job_ids))).all()] if candidate_ids or job_ids else []
        if submission_ids:
            db.query(SubmissionStatusHistory).filter(SubmissionStatusHistory.submission_id.in_(submission_ids)).delete(synchronize_session=False)
            db.query(Submission).filter(Submission.id.in_(submission_ids)).delete(synchronize_session=False)
        if candidate_ids:
            db.query(Candidate).filter(Candidate.id.in_(candidate_ids)).delete(synchronize_session=False)
        if job_ids:
            db.query(Job).filter(Job.id.in_(job_ids)).delete(synchronize_session=False)
        if vendor_ids:
            db.query(VendorContact).filter(VendorContact.vendor_id.in_(vendor_ids)).delete(synchronize_session=False)
        if recruiter_ids:
            db.query(Recruiter).filter(Recruiter.id.in_(recruiter_ids)).delete(synchronize_session=False)
            db.query(Vendor).filter(Vendor.id.in_(vendor_ids)).delete(synchronize_session=False)
        db.query(User).filter(User.email.like(f"{_PREFIX}%")).delete(synchronize_session=False)
        if company_ids:
            db.query(Company).filter(Company.id.in_(company_ids)).delete(synchronize_session=False)
        db.commit()
    finally:
        db.close()


def test_candidate_hotlist_search_filters_and_marks_unavailable_fields(records):
    headers = _headers(records["recruiter_id"])
    response = client.get(
        "/candidates/hotlist?q=Casey%20Rivera&location=Seattle&experience=8&visa_status=H1B&availability_status=Available&rate=100",
        headers=headers,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    candidate = payload["items"][0]["candidate"]
    availability = payload["items"][0]["data_availability"]
    assert candidate["id"] == records["candidate_id"]
    assert availability["current_location"] == "stored"
    assert availability["skills"] == "unavailable"
    assert availability["resume_content"] == "unavailable"


def test_candidate_hotlist_tenant_counts_and_existing_admin_scope(records):
    recruiter_results = client.get("/candidates/hotlist?q=Candidate", headers=_headers(records["recruiter_id"])).json()
    company_results = client.get("/candidates/hotlist?page_size=1", headers=_headers(records["company_admin_id"])).json()
    admin_results = client.get("/candidates/hotlist", headers=_headers(records["global_admin_id"])).json()

    assert recruiter_results["total"] == 1
    assert [item["candidate"]["id"] for item in recruiter_results["items"]] == [records["candidate_id"]]
    assert company_results["total"] == 2
    assert len(company_results["items"]) == 1
    assert admin_results["total"] == 0
    assert client.get("/candidates/hotlist").status_code == 401


def test_vendor_search_filters_jobs_company_domain_and_is_duplicate_safe(records):
    headers = _headers(records["recruiter_id"])
    response = client.get(
        "/vendors/intelligence?company=Sprint%2011%20Test%20Company&website=sprint11.example&location=Seattle&engagement_type=Contract&source=greenhouse&has_jobs=true&active_within_days=30",
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert response.json()["items"][0]["id"] == records["vendor_id"]

    duplicate_matches = client.get("/vendors/intelligence?q=Search%20Contact", headers=headers).json()
    assert duplicate_matches["total"] == 1
    assert [item["id"] for item in duplicate_matches["items"]] == [records["vendor_id"]]


def test_vendor_search_counts_and_contacts_obey_tenant_scope(records):
    headers = _headers(records["recruiter_id"])
    results = client.get("/vendors/intelligence?page_size=1", headers=headers).json()

    assert results["total"] == 2
    assert len(results["items"]) == 1
    assert client.get(f"/vendors/{records['foreign_vendor_id']}/contacts", headers=headers).status_code == 404


def test_vendor_activity_exposes_only_authorized_submission_context(records):
    recruiter_profile = client.get(
        f"/vendors/{records['vendor_id']}/intelligence", headers=_headers(records["recruiter_id"])
    ).json()
    admin_profile = client.get(
        f"/vendors/{records['vendor_id']}/intelligence", headers=_headers(records["company_admin_id"])
    ).json()
    global_admin_profile = client.get(
        f"/vendors/{records['vendor_id']}/intelligence", headers=_headers(records["global_admin_id"])
    ).json()

    assert recruiter_profile["summary"]["total_jobs"] == 1
    assert recruiter_profile["summary"]["contact_count"] == 2
    assert recruiter_profile["summary"]["submission_count"] == 1
    assert recruiter_profile["summary"]["latest_submission_activity"] is not None
    assert recruiter_profile["recent_submissions"][0]["candidate_id"] == records["candidate_id"]
    assert recruiter_profile["recent_submissions"][0]["status"] == "REVIEWING"
    assert len(admin_profile["recent_submissions"]) == 2
    assert global_admin_profile["summary"]["submission_count"] == 0
    assert global_admin_profile["recent_submissions"] == []


def test_existing_submission_api_includes_vendor_name_only_in_authorized_results(records):
    response = client.get(
        f"/submissions?candidate_id={records['candidate_id']}",
        headers=_headers(records["recruiter_id"]),
    )

    assert response.status_code == 200
    assert response.json()[0]["vendor_name"] == "Sprint 11 Vendor Alpha"
    hidden = client.get(
        f"/submissions?candidate_id={records['teammate_candidate_id']}",
        headers=_headers(records["recruiter_id"]),
    )
    assert hidden.status_code == 200
    assert hidden.json() == []