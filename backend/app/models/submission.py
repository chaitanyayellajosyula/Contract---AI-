from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class SubmissionStatus(str, Enum):
    SUBMITTED = "SUBMITTED"
    REVIEWING = "REVIEWING"
    INTERVIEW = "INTERVIEW"
    REJECTED = "REJECTED"
    PLACED = "PLACED"


class Submission(Base):
    """A candidate submitted to a company-owned job."""

    __tablename__ = "submissions"
    __table_args__ = (UniqueConstraint("candidate_id", "job_id", name="uq_submissions_candidate_job"),)

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    candidate_id: Mapped[int] = mapped_column(ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False, index=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False, index=True)
    submitted_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(50), default=SubmissionStatus.SUBMITTED.value, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    candidate: Mapped["Candidate"] = relationship(back_populates="submissions")
    job: Mapped["Job"] = relationship(back_populates="submissions")
    company: Mapped["Company"] = relationship(back_populates="submissions")
    submitted_by: Mapped["User"] = relationship()
