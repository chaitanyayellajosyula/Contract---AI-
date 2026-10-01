from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.candidate import Candidate
from app.models.job import Job
from app.models.outreach import Outreach, OutreachStatus
from app.models.user import User, UserRole
from app.models.vendor import Vendor
from app.models.vendor_contact import VendorContact
from app.schemas.outreach import (
    OutreachDraftCreate,
    OutreachDraftPreview,
    OutreachDraftPreviewRequest,
    OutreachPage,
    OutreachResponse,
    OutreachUpdate,
)
from app.services.candidate_service import CandidateService
from app.services.submission_service import SubmissionService
from app.services.vendor_intelligence_service import VendorIntelligenceService


_ACTIVE_STATUSES = (OutreachStatus.DRAFT.value, OutreachStatus.READY.value)
_MANAGER_ROLES = {UserRole.RECRUITER.value, UserRole.COMPANY_ADMIN.value}


class OutreachService:
    """Draft and track manually-sent outreach using authorized stored records."""

    def __init__(self, db: Session):
        self.db = db

    def preview(self, user: User, payload: OutreachDraftPreviewRequest) -> OutreachDraftPreview:
        entities = self._resolve_entities(user, payload, payload.template_type)
        subject, body, evidence = self._compose(payload.template_type, **entities)
        return OutreachDraftPreview(
            template_type=payload.template_type,
            subject=subject,
            body=body,
            recipient_email=entities["contact"].email if entities["contact"] else None,
            evidence=evidence,
        )

    def create_draft(self, user: User, payload: OutreachDraftCreate) -> OutreachResponse:
        entities = self._resolve_entities(user, payload)
        subject = payload.subject.strip()
        body = payload.body.strip()
        if not subject or not body:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Subject and body cannot be empty")
        duplicate_query = self.db.query(Outreach).filter(
            Outreach.company_id == entities["company_id"],
            Outreach.status.in_(_ACTIVE_STATUSES),
        )
        relationship_key = (payload.candidate_id, payload.job_id, payload.contact_id)
        if any(value is not None for value in relationship_key):
            for field, value in zip(("candidate_id", "job_id", "contact_id"), relationship_key):
                column = getattr(Outreach, field)
                duplicate_query = duplicate_query.filter(column == value if value is not None else column.is_(None))
        else:
            duplicate_query = duplicate_query.filter(Outreach.vendor_id == entities["vendor"].id)
        if duplicate_query.first() is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="An active draft already exists for this relationship",
            )

        outreach = Outreach(
            company_id=entities["company_id"],
            candidate_id=payload.candidate_id,
            job_id=payload.job_id,
            vendor_id=entities["vendor"].id if entities["vendor"] else None,
            contact_id=entities["contact"].id if entities["contact"] else None,
            created_by_user_id=user.id,
            subject=subject,
            body=body,
            notes=payload.notes,
            status=OutreachStatus.DRAFT.value,
        )
        self.db.add(outreach)
        self.db.commit()
        self.db.refresh(outreach)
        return self._response(outreach)

    def list_for_user(
        self,
        user: User,
        *,
        candidate_id: int | None = None,
        job_id: int | None = None,
        vendor_id: int | None = None,
        contact_id: int | None = None,
        status_filter: str | None = None,
        page: int = 1,
        page_size: int = 25,
    ) -> OutreachPage:
        query = self._visible_query(user)
        for column, value in (
            (Outreach.candidate_id, candidate_id),
            (Outreach.job_id, job_id),
            (Outreach.vendor_id, vendor_id),
            (Outreach.contact_id, contact_id),
            (Outreach.status, status_filter),
        ):
            if value is not None:
                query = query.filter(column == value)
        total = query.count()
        records = query.order_by(Outreach.created_at.desc(), Outreach.id.desc()).offset(
            (page - 1) * page_size
        ).limit(page_size).all()
        return OutreachPage(items=[self._response(record) for record in records], total=total, page=page, page_size=page_size)

    def get_for_user(self, outreach_id: int, user: User) -> Outreach | None:
        return self._visible_query(user).filter(Outreach.id == outreach_id).first()

    def update_for_user(self, outreach_id: int, user: User, payload: OutreachUpdate) -> OutreachResponse | None:
        outreach = self.get_for_user(outreach_id, user)
        if outreach is None:
            return None
        if outreach.status not in _ACTIVE_STATUSES:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Only draft or ready outreach can be edited")
        updates = payload.model_dump(exclude_unset=True)
        for field in ("subject", "body"):
            if field in updates:
                value = updates[field]
                if value is None or not value.strip():
                    raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"{field} cannot be empty")
                updates[field] = value.strip()
        for field, value in updates.items():
            if value is not None or field == "notes":
                setattr(outreach, field, value)
        outreach.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(outreach)
        return self._response(outreach)

    def mark_sent(self, outreach_id: int, user: User) -> OutreachResponse | None:
        outreach = self.get_for_user(outreach_id, user)
        if outreach is None:
            return None
        if outreach.status not in _ACTIVE_STATUSES:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Only draft or ready outreach can be marked sent")
        outreach.status = OutreachStatus.SENT.value
        outreach.sent_at = datetime.utcnow()
        outreach.updated_at = outreach.sent_at
        self.db.commit()
        self.db.refresh(outreach)
        return self._response(outreach)

    def cancel(self, outreach_id: int, user: User) -> OutreachResponse | None:
        outreach = self.get_for_user(outreach_id, user)
        if outreach is None:
            return None
        if outreach.status not in _ACTIVE_STATUSES:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Only draft or ready outreach can be cancelled")
        outreach.status = OutreachStatus.CANCELLED.value
        outreach.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(outreach)
        return self._response(outreach)

    def _resolve_entities(self, user: User, payload, template_type: str | None = None) -> dict:
        is_admin = user.role == UserRole.LEGACY_ADMIN.value
        if not is_admin and (user.role not in _MANAGER_ROLES or user.company_id is None):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to create outreach")

        candidate = None
        if payload.candidate_id is not None:
            candidate = CandidateService(self.db).get_candidate_for_user(payload.candidate_id, user)
            if candidate is None:
                raise self._not_found()

        job = self.db.get(Job, payload.job_id) if payload.job_id is not None else None
        if payload.job_id is not None and job is None:
            raise self._not_found()
        job_company_id = SubmissionService._job_company_id(job)
        if not is_admin and job_company_id is not None and job_company_id != user.company_id:
            raise self._not_found()

        contact = self.db.get(VendorContact, payload.contact_id) if payload.contact_id is not None else None
        if payload.contact_id is not None and contact is None:
            raise self._not_found()
        vendor_id = payload.vendor_id
        if contact is not None:
            if vendor_id is not None and vendor_id != contact.vendor_id:
                raise self._not_found()
            vendor_id = contact.vendor_id
        if vendor_id is None and job is not None and job.recruiter is not None and job.recruiter.vendor is not None:
            vendor_id = job.recruiter.vendor.id

        vendor = None
        if vendor_id is not None:
            vendor = VendorIntelligenceService(self.db)._visible_vendor(user, vendor_id)
            if vendor is None:
                raise self._not_found()
        if contact is not None and (vendor is None or vendor.id != contact.vendor_id):
            raise self._not_found()

        has_relation = any((candidate, job, vendor, contact))
        if not has_relation:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Select at least one outreach relationship")
        if template_type == "candidate_submission" and (candidate is None or job is None):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Candidate submission drafts require a candidate and job")
        if template_type == "vendor_relationship" and vendor is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Vendor relationship drafts require a vendor")

        companies = {
            company_id
            for company_id in (
                candidate.company_id if candidate else None,
                job_company_id,
                vendor.company_id if vendor else None,
            )
            if company_id is not None
        }
        if len(companies) > 1:
            raise self._not_found()
        if not is_admin:
            company_id = user.company_id
            if candidate is not None and candidate.company_id != company_id:
                raise self._not_found()
        else:
            company_id = next(iter(companies), None)
        if company_id is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Outreach must be associated with a company")

        return {
            "candidate": candidate,
            "job": job,
            "vendor": vendor,
            "contact": contact,
            "company_id": company_id,
        }

    def _visible_query(self, user: User):
        query = self.db.query(Outreach)
        if user.role == UserRole.RECRUITER.value and user.company_id is not None:
            return query.outerjoin(Candidate, Outreach.candidate_id == Candidate.id).filter(
                Outreach.company_id == user.company_id,
                or_(Outreach.candidate_id.is_(None), Candidate.owner_user_id == user.id),
            )
        if user.role == UserRole.COMPANY_ADMIN.value and user.company_id is not None:
            return query.filter(Outreach.company_id == user.company_id)
        if user.role == UserRole.LEGACY_ADMIN.value:
            return query.filter(Outreach.candidate_id.is_(None))
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to access outreach")

    @staticmethod
    def _compose(template_type: str, candidate=None, job=None, vendor=None, contact=None, company_id=None):
        del company_id
        greeting_name = contact.full_name if contact is not None else None
        greeting = f"Hi {greeting_name}," if greeting_name else "Hello,"
        evidence = []
        if contact is not None:
            evidence.append(f"Contact name: {contact.full_name}")
        if template_type == "candidate_submission":
            candidate_name = f"{candidate.first_name} {candidate.last_name}"
            subject = f"Candidate for {job.title}: {candidate_name}"
            body_lines = [greeting, f"I wanted to share {candidate_name} for the {job.title} opportunity."]
            evidence.extend((f"Candidate name: {candidate_name}", f"Job title: {job.title}"))
            if job.location:
                body_lines.append(f"The role is listed in {job.location}.")
                evidence.append(f"Job location: {job.location}")
            if job.employment_type:
                body_lines.append(f"The engagement is listed as {job.employment_type}.")
                evidence.append(f"Job engagement: {job.employment_type}")
            if candidate.current_location:
                body_lines.append(f"The candidate's recorded location is {candidate.current_location}.")
                evidence.append(f"Candidate location: {candidate.current_location}")
            if candidate.total_experience:
                body_lines.append(f"The profile lists {candidate.total_experience} of total experience.")
                evidence.append(f"Candidate experience: {candidate.total_experience}")
            if candidate.availability_status:
                body_lines.append(f"Recorded availability: {candidate.availability_status}.")
                evidence.append(f"Candidate availability: {candidate.availability_status}")
            if candidate.visa_status:
                body_lines.append(f"Recorded work authorization: {candidate.visa_status}.")
                evidence.append(f"Candidate work authorization: {candidate.visa_status}")
            if candidate.expected_rate:
                body_lines.append(f"The expected rate on file is {candidate.expected_rate}.")
                evidence.append(f"Candidate expected rate: {candidate.expected_rate}")
            body_lines.extend(("Would you be open to reviewing the profile?", "Thank you."))
        elif template_type == "vendor_relationship":
            subject = f"Recruiting requirements with {vendor.name}"
            body_lines = [
                greeting,
                f"I wanted to connect regarding current or upcoming requirements with {vendor.name}.",
            ]
            evidence.append(f"Vendor name: {vendor.name}")
            if job is not None:
                body_lines.append(f"I noted the {job.title} requirement.")
                evidence.append(f"Job title: {job.title}")
            body_lines.extend(("If you have a role to discuss, please share the details.", "Thank you."))
        else:
            references = []
            if candidate is not None:
                candidate_name = f"{candidate.first_name} {candidate.last_name}"
                references.append(candidate_name)
                evidence.append(f"Candidate name: {candidate_name}")
            if job is not None:
                references.append(job.title)
                evidence.append(f"Job title: {job.title}")
            if vendor is not None:
                references.append(vendor.name)
                evidence.append(f"Vendor name: {vendor.name}")
            reference_text = f" regarding {', '.join(references)}" if references else " regarding our earlier discussion"
            subject = f"Following up{reference_text}"
            body_lines = [
                greeting,
                f"Following up{reference_text}.",
                "Please let me know if you have an update or would like to discuss next steps.",
                "Thank you.",
            ]
        return subject, "\n\n".join(body_lines), evidence

    @staticmethod
    def _response(outreach: Outreach) -> OutreachResponse:
        candidate = outreach.candidate
        job = outreach.job
        vendor = outreach.vendor
        contact = outreach.contact
        return OutreachResponse(
            id=outreach.id,
            candidate_id=outreach.candidate_id,
            candidate_name=f"{candidate.first_name} {candidate.last_name}" if candidate else None,
            job_id=outreach.job_id,
            job_title=job.title if job else None,
            vendor_id=outreach.vendor_id,
            vendor_name=vendor.name if vendor else None,
            contact_id=outreach.contact_id,
            contact_name=contact.full_name if contact else None,
            recipient_email=contact.email if contact else None,
            subject=outreach.subject,
            body=outreach.body,
            status=outreach.status,
            notes=outreach.notes,
            created_at=outreach.created_at,
            updated_at=outreach.updated_at,
            sent_at=outreach.sent_at,
        )

    @staticmethod
    def _not_found() -> HTTPException:
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Outreach relationship not found")