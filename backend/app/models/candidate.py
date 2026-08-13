from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Candidate(Base):
    """SQLAlchemy model for recruiter candidates associated with a user and company."""

    __tablename__ = "candidates"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    owner_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False, index=True)
    first_name: Mapped[str] = mapped_column(String(255), nullable=False)
    last_name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    linkedin_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    current_location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    preferred_location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    visa_status: Mapped[str | None] = mapped_column(String(100), nullable=True)
    total_experience: Mapped[str | None] = mapped_column(String(100), nullable=True)
    us_experience: Mapped[str | None] = mapped_column(String(100), nullable=True)
    current_rate: Mapped[str | None] = mapped_column(String(100), nullable=True)
    expected_rate: Mapped[str | None] = mapped_column(String(100), nullable=True)
    availability_status: Mapped[str | None] = mapped_column(String(100), nullable=True)
    resume_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    owner: Mapped["User"] = relationship(back_populates="candidates")
    company: Mapped["Company"] = relationship(back_populates="candidates")
