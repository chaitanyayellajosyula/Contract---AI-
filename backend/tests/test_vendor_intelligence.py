from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.core.database import SessionLocal
from app.main import app
from app.models.company import Company
from app.models.job import Job
from app.models.job_user_status import JobUserStatus
from app.models.recruiter import Recruiter
from app.models.user import User, UserRole
from app.models.vendor import Vendor
from app.models.vendor_contact import VendorContact
from app.services.auth_service import AuthService

client = TestClient(app)
_EMAIL_PREFIX = "sprint9-intel-"


def _cleanup() -> None:
    db = SessionLocal()
    try:
        company_ids = [row[0] for row in db.query(Company.id).filter(Company.name.like("S9 Intelligence %")).all()]
        vendor_ids = [row[0] for row in db.query(Vendor.id).filter(Vendor.company_id.in_(company_ids)).all()] if company_ids else []
        recruiter_ids = [
            row[0] for row in db.query(Recruiter.id).filter(Recruiter.vendor_id.in_(vendor_ids)).all()
        ] if vendor_ids else []
        job_ids = []
        if company_ids or recruiter_ids:
            query = db.query(Job.id)
            conditions = []
            if company_ids:
                conditions.append(Job.company_id.in_(company_ids))
            if recruiter_ids:
                conditions.append(Job.recruiter_id.in_(recruiter_ids))
            from sqlalchemy import or_

            job_ids = [row[0] for row in query.filter(or_(*conditions)).all()]
        if job_ids:
            db.query(JobUserStatus).filter(JobUserStatus.job_id.in_(job_ids)).delete(synchronize_session=False)
            db.query(Job).filter(Job.id.in_(job_ids)).delete(synchronize_session=False)
        if vendor_ids:
            db.query(VendorContact).filter(VendorContact.vendor_id.in_(vendor_ids)).delete(synchronize_session=False)
        if recruiter_ids:
            db.query(Recruiter).filter(Recruiter.id.in_(recruiter_ids)).delete(synchronize_session=False)
        if vendor_ids:
            db.query(Vendor).filter(Vendor.id.in_(vendor_ids)).delete(synchronize_session=False)
        db.query(User).filter(User.email.like(f"{_EMAIL_PREFIX}%")).delete(synchronize_session=False)
        if company_ids:
            db.query(Company).filter(Company.id.in_(company_ids)).delete(synchronize_session=False)
        db.commit()
    finally:
        db.close()


@pytest.fixture(autouse=True)
def clean_intelligence_data():
    _cleanup()
    yield
    _cleanup()


def _create_company(name: str, website: str | None = None) -> Company:
    db = SessionLocal()
    try:
        company = Company(
            name=name,
            website=website,
            industry="Software",
            location="Boston, MA",
        )
        db.add(company)
        db.commit()
        db.refresh(company)
        return company
    finally:
        db.close()


def _create_user(email_suffix: str, company: Company | None, role: str = UserRole.RECRUITER.value) -> User:
    db = SessionLocal()
    try:
        user = User(
            full_name=f"Sprint 9 {email_suffix}",
            email=f"{_EMAIL_PREFIX}{email_suffix}@example.test",
            hashed_password="unused-test-password-hash",
            role=role,
            company_id=company.id if company else None,
            is_active=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user
    finally:
        db.close()


def _headers(user_id: int) -> dict[str, str]:
    db = SessionLocal()
    try:
        user = db.get(User, user_id)
        token = AuthService(db).create_access_token(user)
        return {"Authorization": f"Bearer {token}"}
    finally:
        db.close()


def _create_vendor(name: str, company: Company, email: str | None = None) -> Vendor:
    db = SessionLocal()
    try:
        vendor = Vendor(name=name, email=email, phone="555-0100", company_id=company.id)
        db.add(vendor)
        db.commit()
        db.refresh(vendor)
        return vendor
    finally:
        db.close()


def _create_contact(vendor: Vendor, name: str, email: str, designation: str, updated_at: datetime) -> VendorContact:
    db = SessionLocal()
    try:
        contact = VendorContact(
            vendor_id=vendor.id,
            full_name=name,
            email=email,
            phone="555-0123",
            designation=designation,
            is_active=True,
            created_at=updated_at,
            updated_at=updated_at,
        )
        db.add(contact)
        db.commit()
        db.refresh(contact)
        return contact
    finally:
        db.close()


def _create_job(
    title: str,
    now: datetime,
    *,
    source: str,
    vendor: Vendor | None = None,
    company: Company | None = None,
    employment_type: str | None = None,
    location: str | None = None,
    url: str | None = None,
    posted_days_ago: int = 0,
) -> Job:
    db = SessionLocal()
    try:
        recruiter_id = None
        if vendor is not None:
            recruiter = Recruiter(full_name=f"{title} Recruiter", vendor_id=vendor.id)
            db.add(recruiter)
            db.flush()
            recruiter_id = recruiter.id
        job = Job(
            title=title,
            location=location,
            employment_type=employment_type,
            status="active",
            source=source,
            source_job_id=f"s9-{title.lower().replace(' ', '-')}",
            source_url=url,
            source_company=company.name if company else None,
            posted_at=now - timedelta(days=posted_days_ago),
            created_at=now,
            updated_at=now,
            company_id=company.id if company else None,
            recruiter_id=recruiter_id,
        )
        db.add(job)
        db.commit()
        db.refresh(job)
        return job
    finally:
        db.close()


def test_vendor_profile_shows_related_jobs_contacts_and_only_user_job_status():
    now = datetime.utcnow()
    company = _create_company("S9 Intelligence Tenant", "https://tenant.example.test")
    other_company = _create_company("S9 Intelligence Other", "https://other.example.test")
    recruiter = _create_user("recruiter", company)
    other_recruiter = _create_user("other-recruiter", other_company)
    vendor = _create_vendor("Northstar Staffing", company, "ops@northstar.example.test")
    other_vendor = _create_vendor("Other Staffing", other_company)
    _create_contact(vendor, "Avery Contact", "avery@northstar.example.test", "Account Lead", now)
    _create_contact(vendor, "Blair Contact", "blair@northstar.example.test", "Recruiter", now - timedelta(days=3))
    newest_job = _create_job(
        "Northstar Backend", now, source="greenhouse", vendor=vendor,
        employment_type="Full-time", location="Boston, MA",
        url="https://jobs.example.test/role/1", posted_days_ago=1,
    )
    _create_job(
        "Northstar Contract", now, source="lever", vendor=vendor,
        employment_type="Contract", location="Remote", posted_days_ago=4,
    )
    _create_job("Other Tenant Job", now, source="ashby", vendor=other_vendor, company=other_company)
    conflicting_job = _create_job(
        "Conflicting Tenant Job", now, source="ashby", vendor=other_vendor, company=company
    )

    db = SessionLocal()
    try:
        db.add_all([
            JobUserStatus(user_id=recruiter.id, job_id=newest_job.id, saved=True),
            JobUserStatus(user_id=other_recruiter.id, job_id=newest_job.id, hidden=True),
        ])
        db.commit()
    finally:
        db.close()

    response = client.get(f"/vendors/{vendor.id}/intelligence", headers=_headers(recruiter.id))
    assert response.status_code == 200
    payload = response.json()
    assert payload["vendor"]["name"] == "Northstar Staffing"
    assert payload["vendor"]["company_name"] == company.name
    assert payload["summary"]["total_jobs"] == 2
    assert payload["summary"]["recent_jobs"] == 2
    assert payload["summary"]["sources"] == ["greenhouse", "lever"]
    assert payload["summary"]["engagement_types"] == ["Contract", "Full-time"]
    assert payload["summary"]["locations"] == ["Boston, MA", "Remote"]
    assert payload["summary"]["contact_count"] == 2
    assert payload["summary"]["first_observed_job_activity"] <= payload["summary"]["last_observed_job_activity"]
    assert [job["title"] for job in payload["recent_jobs"]] == ["Northstar Backend", "Northstar Contract"]
    assert payload["recent_jobs"][0]["saved"] is True
    assert payload["recent_jobs"][0]["hidden"] is False
    assert payload["recent_jobs"][0]["external_url"] == "https://jobs.example.test/role/1"
    assert conflicting_job.id not in {job["id"] for job in payload["recent_jobs"]}
    assert [contact["full_name"] for contact in payload["contacts"]] == ["Avery Contact", "Blair Contact"]
    assert payload["contacts"][0]["designation"] == "Account Lead"
    assert "linkedin_url" not in payload["contacts"][0]


def test_vendor_job_pagination_filters_newest_first_and_safe_url_handling():
    now = datetime.utcnow()
    company = _create_company("S9 Intelligence Pagination")
    recruiter = _create_user("pagination", company)
    vendor = _create_vendor("Pagination Vendor", company)
    _create_job("Older Role", now, source="lever", vendor=vendor, employment_type="Contract", location="Remote", posted_days_ago=9)
    _create_job(
        "Newest Role", now, source="ashby", vendor=vendor,
        employment_type="Full-time", location="Denver",
        url="https://jobs.example.test/role?token=private", posted_days_ago=1,
    )

    headers = _headers(recruiter.id)
    first_page = client.get(f"/vendors/{vendor.id}/jobs?page=1&page_size=1", headers=headers)
    assert first_page.status_code == 200
    assert first_page.json()["total"] == 2
    assert first_page.json()["items"][0]["title"] == "Newest Role"
    assert first_page.json()["items"][0]["external_url"] is None

    second_page = client.get(
        f"/vendors/{vendor.id}/jobs?page=1&page_size=1&source=lever&engagement_type=Contract",
        headers=headers,
    )
    assert second_page.status_code == 200
    assert second_page.json()["total"] == 1
    assert second_page.json()["items"][0]["title"] == "Older Role"


def test_company_intelligence_aggregates_tenant_jobs_sources_contacts_and_vendors():
    now = datetime.utcnow()
    company = _create_company("S9 Intelligence Company", "https://company.example.test")
    other_company = _create_company("S9 Intelligence Foreign")
    user = _create_user("company-profile", company)
    vendor = _create_vendor("Company Vendor", company)
    _create_contact(vendor, "Company Contact", "company-contact@example.test", "Operations", now)
    _create_job("Direct Company Job", now, source="ashby", company=company, employment_type="Full-time")
    _create_job("Vendor Company Job", now, source="greenhouse", vendor=vendor, employment_type="Contract")
    _create_job("Foreign Company Job", now, source="lever", company=other_company, employment_type="Contract")

    response = client.get(f"/companies/{company.id}/intelligence", headers=_headers(user.id))
    assert response.status_code == 200
    payload = response.json()
    assert payload["company"]["website"] == "https://company.example.test"
    assert payload["summary"]["total_jobs"] == 2
    assert payload["summary"]["sources"] == ["ashby", "greenhouse"]
    assert payload["summary"]["engagement_types"] == ["Contract", "Full-time"]
    assert payload["summary"]["contact_count"] == 1
    assert [item["name"] for item in payload["vendors"]] == ["Company Vendor"]
    assert {job["title"] for job in payload["recent_jobs"]} == {"Direct Company Job", "Vendor Company Job"}

    search = client.get("/companies/intelligence?q=company-contact", headers=_headers(user.id))
    assert search.status_code == 200
    assert [item["id"] for item in search.json()["items"]] == [company.id]
    assert search.json()["items"][0]["vendor_count"] == 1


def test_vendor_search_paginates_and_matches_domains_and_contacts():
    now = datetime.utcnow()
    company = _create_company("S9 Intelligence Search Tenant", "https://acme-domain.example.test")
    other_company = _create_company("S9 Intelligence Search Other", "https://other-domain.example.test")
    vendor_a = _create_vendor("Acme Staffing", company)
    vendor_b = _create_vendor("Beta Staffing", company)
    _create_vendor("Hidden Foreign Vendor", other_company)
    _create_contact(vendor_a, "Searchable Person", "person@search.example.test", "Partner", now)
    admin = _create_user("global-admin", None, UserRole.LEGACY_ADMIN.value)
    recruiter = _create_user("tenant-search", company)

    search_by_contact = client.get("/vendors/intelligence?q=Searchable%20Person", headers=_headers(recruiter.id))
    assert search_by_contact.status_code == 200
    assert [item["id"] for item in search_by_contact.json()["items"]] == [vendor_a.id]

    search_by_domain = client.get("/vendors/intelligence?q=acme-domain", headers=_headers(recruiter.id))
    assert search_by_domain.status_code == 200
    assert {item["id"] for item in search_by_domain.json()["items"]} == {vendor_a.id, vendor_b.id}

    first_page = client.get("/vendors/intelligence?page=1&page_size=1", headers=_headers(admin.id))
    second_page = client.get("/vendors/intelligence?page=2&page_size=1", headers=_headers(admin.id))
    assert first_page.status_code == second_page.status_code == 200
    assert first_page.json()["total"] == 3
    assert first_page.json()["items"][0]["id"] != second_page.json()["items"][0]["id"]
    tenant_items = client.get("/vendors/intelligence", headers=_headers(recruiter.id)).json()["items"]
    assert {item["id"] for item in tenant_items} == {vendor_a.id, vendor_b.id}


def test_company_website_with_embedded_credentials_is_not_returned():
    company = _create_company(
        "S9 Intelligence Unsafe Website",
        "https://profile-user:profile-secret@unsafe.example.test/?token=hidden-token&session_id=hidden-session",
    )
    user = _create_user("unsafe-website", company)
    vendor = _create_vendor("Unsafe Website Vendor", company)

    company_response = client.get(f"/companies/{company.id}/intelligence", headers=_headers(user.id))
    vendor_response = client.get(f"/vendors/{vendor.id}/intelligence", headers=_headers(user.id))
    assert company_response.status_code == vendor_response.status_code == 200
    assert company_response.json()["company"]["website"] is None
    assert vendor_response.json()["vendor"]["company_website"] is None
    assert "profile-secret" not in str(company_response.json())
    assert "hidden-token" not in str(vendor_response.json())
    assert "hidden-session" not in str(company_response.json())


def test_vendor_company_intelligence_authorization_and_empty_not_found_cases():
    company = _create_company("S9 Intelligence Auth")
    other_company = _create_company("S9 Intelligence Auth Foreign")
    recruiter = _create_user("auth-recruiter", company)
    member = _create_user("auth-member", company, UserRole.LEGACY_MEMBER.value)
    admin = _create_user("auth-admin", None, UserRole.LEGACY_ADMIN.value)
    vendor = _create_vendor("Auth Vendor", company)
    foreign_vendor = _create_vendor("Foreign Vendor", other_company)

    assert client.get("/vendors/intelligence").status_code == 401
    assert client.get("/vendors/intelligence", headers=_headers(member.id)).status_code == 403
    assert client.get(f"/vendors/{foreign_vendor.id}/intelligence", headers=_headers(recruiter.id)).status_code == 404
    assert client.get(f"/vendors/{foreign_vendor.id}/contacts", headers=_headers(recruiter.id)).status_code == 404
    assert client.get(f"/companies/{other_company.id}/intelligence", headers=_headers(recruiter.id)).status_code == 404
    assert client.get(f"/companies/{other_company.id}/intelligence", headers=_headers(admin.id)).status_code == 200
    assert client.get(f"/vendors/{vendor.id}/intelligence", headers=_headers(admin.id)).status_code == 200
    assert client.get("/vendors/999999/intelligence", headers=_headers(recruiter.id)).status_code == 404
    assert client.get("/companies/999999/intelligence", headers=_headers(recruiter.id)).status_code == 404

    empty_profile = client.get(f"/vendors/{vendor.id}/intelligence", headers=_headers(recruiter.id))
    assert empty_profile.status_code == 200
    assert empty_profile.json()["summary"]["total_jobs"] == 0
    assert empty_profile.json()["summary"]["sources"] == []
    assert empty_profile.json()["summary"]["engagement_types"] == []
    assert empty_profile.json()["contacts"] == []
    assert empty_profile.json()["recent_jobs"] == []