from datetime import datetime

from pydantic import BaseModel, Field


class IntelligenceContact(BaseModel):
    id: int
    vendor_id: int
    vendor_name: str
    full_name: str
    email: str
    phone: str | None
    designation: str | None
    is_active: bool
    updated_at: datetime


class IntelligenceJob(BaseModel):
    id: int
    title: str
    location: str | None
    employment_type: str | None
    remote_type: str | None
    status: str | None
    source: str | None
    source_company: str | None
    external_url: str | None
    posted_at: datetime | None
    created_at: datetime
    viewed: bool
    saved: bool
    hidden: bool


class ActivitySummary(BaseModel):
    total_jobs: int
    recent_jobs: int
    latest_job_date: datetime | None
    sources: list[str]
    engagement_types: list[str]
    locations: list[str]
    first_observed_job_activity: datetime | None
    last_observed_job_activity: datetime | None
    contact_count: int
    latest_contact_activity: datetime | None
    submission_count: int = 0
    latest_submission_activity: datetime | None = None


class VendorSubmissionActivity(BaseModel):
    submission_id: int
    candidate_id: int
    candidate_name: str
    job_id: int
    job_title: str
    status: str
    updated_at: datetime


class VendorIntelligenceItem(BaseModel):
    id: int
    name: str
    email: str | None
    phone: str | None
    company_id: int | None
    company_name: str | None
    company_website: str | None
    company_industry: str | None
    company_location: str | None
    created_at: datetime
    updated_at: datetime
    contact_count: int
    job_count: int
    latest_activity: datetime | None


class VendorSearchPage(BaseModel):
    items: list[VendorIntelligenceItem]
    total: int
    page: int
    page_size: int


class VendorIntelligenceProfile(BaseModel):
    vendor: VendorIntelligenceItem
    summary: ActivitySummary
    contacts: list[IntelligenceContact]
    recent_jobs: list[IntelligenceJob]
    recent_submissions: list[VendorSubmissionActivity] = Field(default_factory=list)


class CompanyIntelligenceItem(BaseModel):
    id: int
    name: str
    website: str | None
    industry: str | None
    location: str | None
    created_at: datetime
    updated_at: datetime
    vendor_count: int
    job_count: int
    contact_count: int
    latest_activity: datetime | None


class CompanySearchPage(BaseModel):
    items: list[CompanyIntelligenceItem]
    total: int
    page: int
    page_size: int


class CompanyIntelligenceProfile(BaseModel):
    company: CompanyIntelligenceItem
    summary: ActivitySummary
    vendors: list[VendorIntelligenceItem]
    contacts: list[IntelligenceContact]
    recent_jobs: list[IntelligenceJob]


class IntelligenceJobPage(BaseModel):
    items: list[IntelligenceJob]
    total: int
    page: int
    page_size: int