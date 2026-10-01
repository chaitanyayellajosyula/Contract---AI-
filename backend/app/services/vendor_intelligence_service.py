from datetime import datetime, timedelta
import re
from typing import Any, Callable
from urllib.parse import parse_qsl, urlsplit

from fastapi import HTTPException, status
from sqlalchemy import and_, case, func, or_
from sqlalchemy.orm import Session

from app.models.company import Company
from app.models.job import Job
from app.models.job_user_status import JobUserStatus
from app.models.recruiter import Recruiter
from app.models.user import User, UserRole
from app.models.vendor import Vendor
from app.models.vendor_contact import VendorContact
from app.schemas.vendor_intelligence import (
    ActivitySummary,
    CompanyIntelligenceItem,
    CompanyIntelligenceProfile,
    CompanySearchPage,
    IntelligenceContact,
    IntelligenceJob,
    IntelligenceJobPage,
    VendorIntelligenceItem,
    VendorIntelligenceProfile,
    VendorSearchPage,
)

RECENT_ACTIVITY_WINDOW = timedelta(days=30)
RECENT_JOB_LIMIT = 10
_SENSITIVE_URL_KEYS = {"auth", "authorization", "credential", "key", "password", "secret", "session", "sig", "signature"}
_MANAGER_ROLES = {UserRole.RECRUITER.value, UserRole.COMPANY_ADMIN.value}


class VendorIntelligenceService:
    """Read-only vendor/company intelligence derived from existing persisted records."""

    def __init__(self, db: Session, clock: Callable[[], datetime] | None = None):
        self.db = db
        self.clock = clock or datetime.utcnow

    def search_vendors(
        self,
        user: User,
        query: str | None,
        page: int,
        page_size: int,
    ) -> VendorSearchPage:
        company_scope = self._company_scope(user)
        vendor_query = self.db.query(Vendor).outerjoin(Company, Vendor.company_id == Company.id)
        if company_scope is not None:
            vendor_query = vendor_query.filter(Vendor.company_id == company_scope)
        search = (query or "").strip()
        if search:
            pattern = f"%{search}%"
            vendor_query = vendor_query.filter(or_(
                Vendor.name.ilike(pattern),
                Vendor.email.ilike(pattern),
                Company.website.ilike(pattern),
                Vendor.contacts.any(or_(VendorContact.full_name.ilike(pattern), VendorContact.email.ilike(pattern))),
            ))
        total = vendor_query.distinct().count()
        vendors = vendor_query.distinct().order_by(Vendor.name.asc(), Vendor.id.asc()).offset(
            (page - 1) * page_size
        ).limit(page_size).all()
        return VendorSearchPage(
            items=[self._vendor_item(vendor) for vendor in vendors],
            total=total,
            page=page,
            page_size=page_size,
        )

    def vendor_profile(self, user: User, vendor_id: int) -> VendorIntelligenceProfile | None:
        vendor = self._visible_vendor(user, vendor_id)
        if vendor is None:
            return None
        contacts = self._vendor_contacts(vendor)
        jobs_query = self._vendor_jobs_query(vendor)
        summary = self._activity_summary(jobs_query, contacts)
        recent_jobs = jobs_query.order_by(
            func.coalesce(Job.posted_at, Job.created_at).desc(), Job.id.desc()
        ).limit(RECENT_JOB_LIMIT).all()
        return VendorIntelligenceProfile(
            vendor=self._vendor_item(vendor),
            summary=summary,
            contacts=contacts,
            recent_jobs=self._serialize_jobs(recent_jobs, user),
        )

    def vendor_jobs(
        self,
        user: User,
        vendor_id: int,
        page: int,
        page_size: int,
        source: str | None = None,
        engagement_type: str | None = None,
        location: str | None = None,
    ) -> IntelligenceJobPage | None:
        vendor = self._visible_vendor(user, vendor_id)
        if vendor is None:
            return None
        query = self._vendor_jobs_query(vendor)
        if source:
            query = query.filter(Job.source == source)
        if engagement_type:
            query = query.filter(Job.employment_type == engagement_type)
        if location:
            query = query.filter(Job.location.ilike(f"%{location.strip()}%"))
        total = query.count()
        jobs = query.order_by(
            func.coalesce(Job.posted_at, Job.created_at).desc(), Job.id.desc()
        ).offset((page - 1) * page_size).limit(page_size).all()
        return IntelligenceJobPage(
            items=self._serialize_jobs(jobs, user),
            total=total,
            page=page,
            page_size=page_size,
        )

    def vendor_contacts(self, user: User, vendor_id: int) -> list[IntelligenceContact] | None:
        vendor = self._visible_vendor(user, vendor_id)
        return self._vendor_contacts(vendor) if vendor is not None else None

    def search_companies(
        self,
        user: User,
        query: str | None,
        page: int,
        page_size: int,
    ) -> CompanySearchPage:
        company_query = self._visible_companies_query(user)
        search = (query or "").strip()
        if search:
            pattern = f"%{search}%"
            company_query = company_query.filter(or_(
                Company.name.ilike(pattern),
                Company.website.ilike(pattern),
                Company.industry.ilike(pattern),
                Company.vendors.any(or_(
                    Vendor.name.ilike(pattern),
                    Vendor.contacts.any(or_(VendorContact.full_name.ilike(pattern), VendorContact.email.ilike(pattern))),
                )),
            ))
        total = company_query.distinct().count()
        companies = company_query.distinct().order_by(Company.name.asc(), Company.id.asc()).offset(
            (page - 1) * page_size
        ).limit(page_size).all()
        return CompanySearchPage(
            items=[self._company_item(company) for company in companies],
            total=total,
            page=page,
            page_size=page_size,
        )

    def company_profile(self, user: User, company_id: int) -> CompanyIntelligenceProfile | None:
        company = self._visible_companies_query(user).filter(Company.id == company_id).first()
        if company is None:
            return None
        vendors = self.db.query(Vendor).filter(Vendor.company_id == company.id).order_by(
            Vendor.name.asc(), Vendor.id.asc()
        ).all()
        contacts = [contact for vendor in vendors for contact in self._vendor_contacts(vendor)]
        jobs_query = self._company_jobs_query(company.id)
        summary = self._activity_summary(jobs_query, contacts)
        jobs = jobs_query.order_by(func.coalesce(Job.posted_at, Job.created_at).desc(), Job.id.desc()).limit(
            RECENT_JOB_LIMIT
        ).all()
        return CompanyIntelligenceProfile(
            company=self._company_item(company),
            summary=summary,
            vendors=[self._vendor_item(vendor) for vendor in vendors],
            contacts=contacts,
            recent_jobs=self._serialize_jobs(jobs, user),
        )

    def company_jobs(
        self,
        user: User,
        company_id: int,
        page: int,
        page_size: int,
        source: str | None = None,
        engagement_type: str | None = None,
        location: str | None = None,
    ) -> IntelligenceJobPage | None:
        company = self._visible_companies_query(user).filter(Company.id == company_id).first()
        if company is None:
            return None
        query = self._company_jobs_query(company.id)
        if source:
            query = query.filter(Job.source == source)
        if engagement_type:
            query = query.filter(Job.employment_type == engagement_type)
        if location:
            query = query.filter(Job.location.ilike(f"%{location.strip()}%"))
        total = query.count()
        jobs = query.order_by(func.coalesce(Job.posted_at, Job.created_at).desc(), Job.id.desc()).offset(
            (page - 1) * page_size
        ).limit(page_size).all()
        return IntelligenceJobPage(
            items=self._serialize_jobs(jobs, user),
            total=total,
            page=page,
            page_size=page_size,
        )

    def _company_scope(self, user: User) -> int | None:
        if user.role == UserRole.LEGACY_ADMIN.value:
            return None
        if user.role in _MANAGER_ROLES and user.company_id is not None:
            return user.company_id
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to access vendor intelligence")

    def _visible_vendor(self, user: User, vendor_id: int) -> Vendor | None:
        company_scope = self._company_scope(user)
        query = self.db.query(Vendor).filter(Vendor.id == vendor_id)
        if company_scope is not None:
            query = query.filter(Vendor.company_id == company_scope)
        return query.first()

    def _visible_companies_query(self, user: User):
        company_scope = self._company_scope(user)
        query = self.db.query(Company)
        if company_scope is not None:
            query = query.filter(Company.id == company_scope)
        return query

    def _vendor_item(self, vendor: Vendor) -> VendorIntelligenceItem:
        contacts = self._vendor_contacts(vendor)
        jobs_query = self._vendor_jobs_query(vendor)
        activity = self._job_activity(jobs_query)
        latest_contact = max((contact.updated_at for contact in contacts), default=None)
        company = vendor.company
        return VendorIntelligenceItem(
            id=vendor.id,
            name=vendor.name,
            email=vendor.email,
            phone=vendor.phone,
            company_id=vendor.company_id,
            company_name=company.name if company else None,
            company_website=self._safe_website(company.website) if company else None,
            company_industry=company.industry if company else None,
            company_location=company.location if company else None,
            created_at=vendor.created_at,
            updated_at=vendor.updated_at,
            contact_count=len(contacts),
            job_count=activity["total_jobs"],
            latest_activity=max(activity["last_observed_job_activity"] or datetime.min, latest_contact or datetime.min)
            if activity["last_observed_job_activity"] is not None or latest_contact is not None
            else None,
        )

    def _company_item(self, company: Company) -> CompanyIntelligenceItem:
        vendors = self.db.query(Vendor).filter(Vendor.company_id == company.id).all()
        contacts = [contact for vendor in vendors for contact in self._vendor_contacts(vendor)]
        activity = self._job_activity(self._company_jobs_query(company.id))
        latest_contact = max((contact.updated_at for contact in contacts), default=None)
        last_job = activity["last_observed_job_activity"]
        latest_activity = max(last_job, latest_contact) if last_job and latest_contact else last_job or latest_contact
        return CompanyIntelligenceItem(
            id=company.id,
            name=company.name,
            website=self._safe_website(company.website),
            industry=company.industry,
            location=company.location,
            created_at=company.created_at,
            updated_at=company.updated_at,
            vendor_count=len(vendors),
            job_count=activity["total_jobs"],
            contact_count=len(contacts),
            latest_activity=latest_activity,
        )

    def _activity_summary(self, jobs_query, contacts: list[IntelligenceContact]) -> ActivitySummary:
        activity = self._job_activity(jobs_query)
        latest_contact = max((contact.updated_at for contact in contacts), default=None)
        return ActivitySummary(
            **activity,
            contact_count=len(contacts),
            latest_contact_activity=latest_contact,
        )

    def _job_activity(self, query) -> dict[str, Any]:
        activity_at = func.coalesce(Job.posted_at, Job.created_at)
        now = self.clock()
        cutoff = now - RECENT_ACTIVITY_WINDOW
        row = query.with_entities(
            func.count(Job.id),
            func.sum(case((activity_at >= cutoff, 1), else_=0)),
            func.max(activity_at),
            func.min(activity_at),
        ).first()
        sources = [value for (value,) in query.with_entities(Job.source).distinct().order_by(Job.source).all() if value]
        engagement_types = [
            value for (value,) in query.with_entities(Job.employment_type).distinct().order_by(Job.employment_type).all()
            if value
        ]
        locations = [value for (value,) in query.with_entities(Job.location).distinct().order_by(Job.location).all() if value]
        return {
            "total_jobs": int(row[0] or 0),
            "recent_jobs": int(row[1] or 0),
            "latest_job_date": row[2],
            "sources": sources,
            "engagement_types": engagement_types,
            "locations": locations,
            "first_observed_job_activity": row[3],
            "last_observed_job_activity": row[2],
        }

    def _vendor_jobs_query(self, vendor: Vendor):
        return self.db.query(Job).join(Recruiter, Job.recruiter_id == Recruiter.id).filter(
            Recruiter.vendor_id == vendor.id,
            or_(Job.company_id.is_(None), Job.company_id == vendor.company_id),
        )

    def _company_jobs_query(self, company_id: int):
        return self.db.query(Job).outerjoin(Recruiter, Job.recruiter_id == Recruiter.id).outerjoin(
            Vendor, Recruiter.vendor_id == Vendor.id
        ).filter(or_(
            Job.company_id == company_id,
            and_(Job.company_id.is_(None), Vendor.company_id == company_id),
        )).distinct()

    def _vendor_contacts(self, vendor: Vendor) -> list[IntelligenceContact]:
        contacts = self.db.query(VendorContact).filter(VendorContact.vendor_id == vendor.id).order_by(
            VendorContact.full_name.asc(), VendorContact.id.asc()
        ).all()
        return [
            IntelligenceContact(
                id=contact.id,
                vendor_id=contact.vendor_id,
                vendor_name=vendor.name,
                full_name=contact.full_name,
                email=contact.email,
                phone=contact.phone,
                designation=contact.designation,
                is_active=contact.is_active,
                updated_at=contact.updated_at,
            )
            for contact in contacts
        ]

    def _serialize_jobs(self, jobs: list[Job], user: User) -> list[IntelligenceJob]:
        if not jobs:
            return []
        job_ids = [job.id for job in jobs]
        statuses = {
            item.job_id: item
            for item in self.db.query(JobUserStatus).filter(
                JobUserStatus.user_id == user.id,
                JobUserStatus.job_id.in_(job_ids),
            ).all()
        }
        serialized = []
        for job in jobs:
            user_status = statuses.get(job.id)
            serialized.append(IntelligenceJob(
                id=job.id,
                title=job.title,
                location=job.location,
                employment_type=job.employment_type,
                remote_type=job.remote_type,
                status=job.status,
                source=job.source,
                source_company=job.source_company,
                external_url=self._safe_external_url(job.source_url),
                posted_at=job.posted_at,
                created_at=job.created_at,
                viewed=user_status.viewed if user_status else False,
                saved=user_status.saved if user_status else False,
                hidden=user_status.hidden if user_status else False,
            ))
        return serialized

    @staticmethod
    def _safe_external_url(value: str | None) -> str | None:
        if not value:
            return None
        try:
            parsed = urlsplit(value)
            if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
                return None
            if VendorIntelligenceService._has_sensitive_query(parsed.query):
                return None
        except ValueError:
            return None
        return value

    @staticmethod
    def _safe_website(value: str | None) -> str | None:
        if not value:
            return None
        candidate = value if "://" in value else f"//{value}"
        try:
            parsed = urlsplit(candidate)
            if not parsed.hostname or parsed.username or parsed.password:
                return None
            if parsed.scheme not in {"", "http", "https"}:
                return None
            hostname = parsed.hostname
            if ":" in hostname and not hostname.startswith("["):
                hostname = f"[{hostname}]"
            port = f":{parsed.port}" if parsed.port is not None else ""
        except ValueError:
            return None
        return f"{parsed.scheme or 'https'}://{hostname}{port}"

    @staticmethod
    def _has_sensitive_query(query: str) -> bool:
        markers = ("token", "secret", "credential", "password", "signature", "apikey", "authorization", "session")
        for key, _ in parse_qsl(query, keep_blank_values=True):
            normalized = re.sub(r"[^a-z0-9]", "", key.lower())
            if normalized in {re.sub(r"[^a-z0-9]", "", item) for item in _SENSITIVE_URL_KEYS}:
                return True
            if any(marker in normalized for marker in markers):
                return True
        return False