from datetime import datetime
from enum import Enum

from sqlalchemy import Boolean, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from app.core.database import Base


class UserRole(str, Enum):
    """Controlled role values for the current Falcon AI authorization foundation."""

    RECRUITER = "RECRUITER"
    COMPANY_ADMIN = "COMPANY_ADMIN"
    LEGACY_MEMBER = "member"
    LEGACY_ADMIN = "ADMIN"


class User(Base):
    """SQLAlchemy model for authenticated application users."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(50), default=UserRole.RECRUITER.value, nullable=False)
    company_id: Mapped[int | None] = mapped_column(ForeignKey("companies.id"), nullable=True, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    company: Mapped["Company | None"] = relationship(back_populates="users")
    candidates: Mapped[list["Candidate"]] = relationship(back_populates="owner", cascade="all, delete-orphan")

    @validates("company_id")
    def validate_company_id(self, key: str, value: int | None) -> int | None:
        """Ensure company assignments are valid positive identifiers when supplied."""
        if value is not None and value <= 0:
            raise ValueError("Company id must be a positive integer")
        return value

    @validates("role")
    def validate_role(self, key: str, value: str | UserRole) -> str:
        """Allow the current valid roles while preserving legacy values already in the database."""
        normalized = value.value if isinstance(value, UserRole) else value
        allowed = {
            UserRole.RECRUITER.value,
            UserRole.COMPANY_ADMIN.value,
            UserRole.LEGACY_MEMBER.value,
            UserRole.LEGACY_ADMIN.value,
        }
        if normalized not in allowed:
            raise ValueError(f"Invalid user role: {normalized}")
        return normalized
