from fastapi.testclient import TestClient
import pytest
from sqlalchemy import or_

from app.core.database import SessionLocal
from app.main import app
from app.models.candidate import Candidate
from app.models.company import Company
from app.models.job import Job
from app.models.outreach import Outreach
from app.models.recruiter import Recruiter
from app.models.user import User, UserRole
from app.models.vendor import Vendor
from app.models.vendor_contact import VendorContact
from app.services.auth_service import AuthService


client = TestClient(app)
PREFIX = "sprint12-"


def _create_data():
    db = SessionLocal()
    try:
        company = Company(name="Sprint 12 Company")
        foreign_company = Company(name="Sprint 12 Foreign Company")
        db.add_all([company, foreign_company])
        db.flush()
        recruiter = User(
            full_name="Sprint 12 Recruiter",
            email=f"{PREFIX}recruiter@example.test",
            hashed_password="test-hash",
            role=UserRole.RECRUITER.value,
            company_id=company.id,
        )
        teammate = User(
            full_name="Sprint 12 Teammate",
            email=f"{PREFIX}teammate@example.test",
            hashed_password="test-hash",
            role=UserRole.RECRUITER.value,
            company_id=company.id,
        )
        company_admin = User(
            full_name="Sprint 12 Company Admin",
            email=f"{PREFIX}company-admin@example.test",
            hashed_password="test-hash",
            role=UserRole.COMPANY_ADMIN.value,
            company_id=company.id,
        )
        foreign_user = User(
            full_name="Sprint 12 Foreign Recruiter",
            email=f"{PREFIX}foreign@example.test",
            hashed_password="test-hash",
            role=UserRole.RECRUITER.value,
            company_id=foreign_company.id,
        )
        global_admin = User(
            full_name="Sprint 12 Global Admin",
            email=f"{PREFIX}admin@example.test",
            hashed_password="test-hash",
            role=UserRole.LEGACY_ADMIN.value,
        )
        db.add_all([recruiter, teammate, company_admin, foreign_user, global_admin])
        db.flush()
        candidate = Candidate(
            owner_user_id=recruiter.id,
            company_id=company.id,
            first_name="Avery",
            last_name="Candidate",
            email=f"{PREFIX}candidate@example.test",
            current_location="Austin, TX",
            total_experience="7 years",
            visa_status="H1B",
            availability_status="Available",
            expected_rate="$100/hour",
        )
        missing_data_candidate = Candidate(
            owner_user_id=recruiter.id,
            company_id=company.id,
            first_name="Jordan",
            last_name="Profile",
            email=f"{PREFIX}missing@example.test",
        )
        teammate_candidate = Candidate(
            owner_user_id=teammate.id,
            company_id=company.id,
            first_name="Taylor",
            last_name="Teammate",
            email=f"{PREFIX}teammate-candidate@example.test",
        )
        foreign_candidate = Candidate(
            owner_user_id=foreign_user.id,
            company_id=foreign_company.id,
            first_name="Morgan",
            last_name="Foreign",
            email=f"{PREFIX}foreign-candidate@example.test",
        )
        vendor = Vendor(name="Sprint 12 Vendor", company_id=company.id)
        other_vendor = Vendor(name="Sprint 12 Vendor Other", company_id=company.id)
        foreign_vendor = Vendor(name="Sprint 12 Foreign Vendor", company_id=foreign_company.id)
        db.add_all([candidate, missing_data_candidate, teammate_candidate, foreign_candidate, vendor, other_vendor, foreign_vendor])
        db.flush()
        vendor_recruiter = Recruiter(full_name="Sprint 12 Vendor Recruiter", vendor_id=vendor.id)
        foreign_vendor_recruiter = Recruiter(full_name="Sprint 12 Foreign Vendor Recruiter", vendor_id=foreign_vendor.id)
        db.add_all([vendor_recruiter, foreign_vendor_recruiter])
        db.flush()
        contact = VendorContact(
            vendor_id=vendor.id,
            full_name="Sam Contact",
            email=f"{PREFIX}contact@example.test",
        )
        foreign_contact = VendorContact(
            vendor_id=foreign_vendor.id,
            full_name="Foreign Contact",
            email=f"{PREFIX}foreign-contact@example.test",
        )
        job = Job(
            title="Platform Engineer",
            location="Seattle, WA",
            employment_type="Contract",
            description="Stored role description.",
            recruiter_id=vendor_recruiter.id,
            source="manual",
            source_job_id=f"{PREFIX}job",
        )
        foreign_job = Job(
            title="Foreign Engineer",
            recruiter_id=foreign_vendor_recruiter.id,
            source="manual",
            source_job_id=f"{PREFIX}foreign-job",
        )
        sparse_job = Job(title="General Role", source="manual", source_job_id=f"{PREFIX}sparse-job")
        db.add_all([contact, foreign_contact, job, foreign_job, sparse_job])
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
            "missing_data_candidate_id": missing_data_candidate.id,
            "teammate_candidate_id": teammate_candidate.id,
            "foreign_candidate_id": foreign_candidate.id,
            "vendor_id": vendor.id,
            "other_vendor_id": other_vendor.id,
            "foreign_vendor_id": foreign_vendor.id,
            "contact_id": contact.id,
            "foreign_contact_id": foreign_contact.id,
            "job_id": job.id,
            "foreign_job_id": foreign_job.id,
            "sparse_job_id": sparse_job.id,
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
    data = _create_data()
    yield data
    db = SessionLocal()
    try:
        company_ids = [row[0] for row in db.query(Company.id).filter(Company.name.like("Sprint 12 %")).all()]
        candidate_ids = [row[0] for row in db.query(Candidate.id).filter(Candidate.email.like(f"{PREFIX}%")).all()]
        vendor_ids = [row[0] for row in db.query(Vendor.id).filter(Vendor.name.like("Sprint 12 %")).all()]
        recruiter_ids = [row[0] for row in db.query(Recruiter.id).filter(Recruiter.vendor_id.in_(vendor_ids)).all()] if vendor_ids else []
        job_ids = [row[0] for row in db.query(Job.id).filter(Job.source_job_id.like(f"{PREFIX}%")).all()]
        if company_ids or candidate_ids:
            outreach_filter = []
            if company_ids:
                outreach_filter.append(Outreach.company_id.in_(company_ids))
            if candidate_ids:
                outreach_filter.append(Outreach.candidate_id.in_(candidate_ids))
            db.query(Outreach).filter(or_(*outreach_filter)).delete(synchronize_session=False)
        if candidate_ids:
            db.query(Candidate).filter(Candidate.id.in_(candidate_ids)).delete(synchronize_session=False)
        if job_ids:
            db.query(Job).filter(Job.id.in_(job_ids)).delete(synchronize_session=False)
        if vendor_ids:
            db.query(VendorContact).filter(VendorContact.vendor_id.in_(vendor_ids)).delete(synchronize_session=False)
        if recruiter_ids:
            db.query(Recruiter).filter(Recruiter.id.in_(recruiter_ids)).delete(synchronize_session=False)
        if vendor_ids:
            db.query(Vendor).filter(Vendor.id.in_(vendor_ids)).delete(synchronize_session=False)
        db.query(User).filter(User.email.like(f"{PREFIX}%")).delete(synchronize_session=False)
        if company_ids:
            db.query(Company).filter(Company.id.in_(company_ids)).delete(synchronize_session=False)
        db.commit()
    finally:
        db.close()


def _preview(headers, **payload):
    return client.post("/outreach/draft-preview", json=payload, headers=headers)


def _create_draft(headers, records, **overrides):
    payload = {
        "candidate_id": records["candidate_id"],
        "job_id": records["job_id"],
        "contact_id": records["contact_id"],
        "subject": "Candidate for Platform Engineer",
        "body": "Edited draft body.",
    }
    payload.update(overrides)
    return client.post("/outreach/drafts", json=payload, headers=headers)


def test_candidate_job_preview_personalizes_contact_job_and_candidate_without_saving(records):
    headers = _headers(records["recruiter_id"])
    response = _preview(
        headers,
        candidate_id=records["candidate_id"],
        job_id=records["job_id"],
        contact_id=records["contact_id"],
        template_type="candidate_submission",
    )

    assert response.status_code == 200
    result = response.json()
    assert result["recipient_email"] == "sprint12-contact@example.test"
    assert "Sam Contact" in result["body"]
    assert "Avery Candidate" in result["body"]
    assert "Platform Engineer" in result["body"]
    assert "Seattle, WA" in result["body"]
    assert "7 years" in result["body"]
    assert "H1B" in result["body"]
    assert any("Job title: Platform Engineer" == value for value in result["evidence"])
    with SessionLocal() as db:
        assert db.query(Outreach).count() == 0


def test_vendor_relationship_template_uses_stored_vendor_and_contact(records):
    result = _preview(
        _headers(records["recruiter_id"]),
        vendor_id=records["vendor_id"],
        contact_id=records["contact_id"],
        template_type="vendor_relationship",
    )

    assert result.status_code == 200
    body = result.json()["body"]
    assert "Sam Contact" in body
    assert "Sprint 12 Vendor" in body
    assert "current or upcoming requirements" in body
    assert "sprint12-contact@example.test" not in body


def test_follow_up_template_uses_selected_relationships(records):
    result = _preview(
        _headers(records["recruiter_id"]),
        candidate_id=records["candidate_id"],
        job_id=records["job_id"],
        template_type="follow_up",
    )

    assert result.status_code == 200
    assert "Avery Candidate" in result.json()["subject"]
    assert "Platform Engineer" in result.json()["body"]
    assert "earlier discussion" not in result.json()["body"]


def test_missing_candidate_and_job_fields_are_omitted_not_fabricated(records):
    result = _preview(
        _headers(records["recruiter_id"]),
        candidate_id=records["missing_data_candidate_id"],
        job_id=records["sparse_job_id"],
        template_type="candidate_submission",
    )

    assert result.status_code == 200
    body = result.json()["body"]
    assert "Jordan Profile" in body
    assert "General Role" in body
    assert "Not recorded" not in body
    assert "unknown" not in body.lower()
    assert "skills" not in body.lower()
    assert "visa" not in body.lower()
    assert "rate" not in body.lower()


def test_preview_rejects_template_without_required_entities(records):
    response = _preview(_headers(records["recruiter_id"]), template_type="candidate_submission")

    assert response.status_code == 400


def test_draft_rejects_blank_subject_or_body(records):
    headers = _headers(records["recruiter_id"])
    blank_subject = _create_draft(headers, records, subject="   ")
    blank_body = _create_draft(headers, records, body="   ")

    assert blank_subject.status_code == 422
    assert blank_body.status_code == 422


def test_draft_save_edit_and_history(records):
    headers = _headers(records["recruiter_id"])
    created = _create_draft(headers, records)

    assert created.status_code == 201
    outreach = created.json()
    assert outreach["status"] == "DRAFT"
    assert outreach["vendor_name"] == "Sprint 12 Vendor"
    assert outreach["contact_name"] == "Sam Contact"
    assert outreach["recipient_email"] == "sprint12-contact@example.test"
    assert "created_by_user_id" not in outreach

    updated = client.patch(
        f"/outreach/{outreach['id']}",
        json={"subject": "Reviewed subject", "body": "Reviewed body", "status": "READY"},
        headers=headers,
    )
    assert updated.status_code == 200
    assert updated.json()["subject"] == "Reviewed subject"
    assert updated.json()["status"] == "READY"
    assert _create_draft(headers, records).status_code == 409

    history = client.get(f"/outreach?candidate_id={records['candidate_id']}&page_size=1", headers=headers)
    assert history.status_code == 200
    assert history.json()["total"] == 1
    assert history.json()["items"][0]["id"] == outreach["id"]
    assert client.get(f"/outreach/{outreach['id']}", headers=headers).status_code == 200


def test_duplicate_active_draft_is_rejected_but_sent_outreach_allows_follow_up(records):
    headers = _headers(records["recruiter_id"])
    first = _create_draft(headers, records)
    duplicate = _create_draft(headers, records)
    assert first.status_code == 201
    assert duplicate.status_code == 409

    sent = client.post(f"/outreach/{first.json()['id']}/mark-sent", headers=headers)
    assert sent.status_code == 200
    assert sent.json()["status"] == "SENT"
    assert sent.json()["sent_at"] is not None
    follow_up = _create_draft(headers, records)
    assert follow_up.status_code == 201


def test_vendor_only_drafts_deduplicate_per_vendor(records):
    headers = _headers(records["recruiter_id"])
    first = _create_draft(headers, records, candidate_id=None, job_id=None, contact_id=None, vendor_id=records["vendor_id"])
    duplicate = _create_draft(headers, records, candidate_id=None, job_id=None, contact_id=None, vendor_id=records["vendor_id"])
    separate_vendor = _create_draft(headers, records, candidate_id=None, job_id=None, contact_id=None, vendor_id=records["other_vendor_id"])

    assert first.status_code == 201
    assert duplicate.status_code == 409
    assert separate_vendor.status_code == 201


def test_cancel_status_and_terminal_state_protection(records):
    headers = _headers(records["recruiter_id"])
    created = _create_draft(headers, records).json()
    cancelled = client.post(f"/outreach/{created['id']}/cancel", headers=headers)

    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "CANCELLED"
    assert client.patch(f"/outreach/{created['id']}", json={"subject": "change"}, headers=headers).status_code == 409
    assert client.post(f"/outreach/{created['id']}/mark-sent", headers=headers).status_code == 409
    assert _create_draft(headers, records).status_code == 201


def test_recruiter_cannot_access_other_candidate_foreign_job_vendor_or_contact(records):
    headers = _headers(records["recruiter_id"])
    unauthorized_candidate = _preview(
        headers,
        candidate_id=records["teammate_candidate_id"],
        job_id=records["job_id"],
        template_type="candidate_submission",
    )
    foreign_job = _preview(
        headers,
        candidate_id=records["candidate_id"],
        job_id=records["foreign_job_id"],
        template_type="candidate_submission",
    )
    foreign_contact = _preview(
        headers,
        vendor_id=records["foreign_vendor_id"],
        contact_id=records["foreign_contact_id"],
        template_type="vendor_relationship",
    )
    mismatch = _preview(
        headers,
        vendor_id=records["vendor_id"],
        contact_id=records["foreign_contact_id"],
        template_type="vendor_relationship",
    )

    assert unauthorized_candidate.status_code == 404
    assert foreign_job.status_code == 404
    assert foreign_contact.status_code == 404
    assert mismatch.status_code == 404


def test_outreach_history_and_details_are_company_and_owner_scoped(records):
    owner_headers = _headers(records["recruiter_id"])
    created = _create_draft(owner_headers, records).json()
    teammate_history = client.get("/outreach", headers=_headers(records["teammate_id"])).json()
    company_history = client.get("/outreach", headers=_headers(records["company_admin_id"])).json()
    foreign_history = client.get("/outreach", headers=_headers(records["foreign_user_id"])).json()

    assert teammate_history["total"] == 0
    assert company_history["total"] == 1
    assert foreign_history["total"] == 0
    assert client.get(f"/outreach/{created['id']}", headers=_headers(records["teammate_id"])).status_code == 404
    assert client.get(f"/outreach/{created['id']}", headers=_headers(records["foreign_user_id"])).status_code == 404


def test_global_admin_can_access_vendor_only_outreach_but_not_candidate_outreach(records):
    owner_headers = _headers(records["recruiter_id"])
    candidate_draft = _create_draft(owner_headers, records)
    admin_headers = _headers(records["global_admin_id"])
    candidate_preview = _preview(
        admin_headers,
        candidate_id=records["candidate_id"],
        job_id=records["job_id"],
        template_type="candidate_submission",
    )
    vendor_preview = _preview(
        admin_headers,
        vendor_id=records["vendor_id"],
        contact_id=records["contact_id"],
        template_type="vendor_relationship",
    )
    saved = client.post(
        "/outreach/drafts",
        json={"vendor_id": records["vendor_id"], "contact_id": records["contact_id"], "subject": "Vendor follow-up", "body": "Manual draft."},
        headers=admin_headers,
    )

    assert candidate_preview.status_code == 404
    assert vendor_preview.status_code == 200
    assert saved.status_code == 201
    admin_history = client.get("/outreach", headers=admin_headers).json()
    assert admin_history["total"] == 1
    assert admin_history["items"][0]["id"] == saved.json()["id"]
    assert client.get(f"/outreach/{candidate_draft.json()['id']}", headers=admin_headers).status_code == 404


def test_unauthenticated_and_existing_api_compatibility(records):
    assert client.post("/outreach/draft-preview", json={"template_type": "follow_up"}).status_code == 401
    headers = _headers(records["recruiter_id"])
    assert client.get("/candidates/hotlist", headers=headers).status_code == 200
    assert client.get("/vendors/intelligence", headers=headers).status_code == 200
    assert client.get("/submissions", headers=headers).status_code == 200