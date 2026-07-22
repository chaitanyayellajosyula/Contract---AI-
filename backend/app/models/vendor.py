from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Vendor(Base):
    """SQLAlchemy model for staffing or recruiting vendors."""

    __tablename__ = "vendors"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    company_id: Mapped[int | None] = mapped_column(ForeignKey("companies.id"), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    company: Mapped["Company"] = relationship(back_populates="vendors")
    recruiters: Mapped[list["Recruiter"]] = relationship(back_populates="vendor", cascade="all, delete-orphan")
    contacts: Mapped[list["VendorContact"]] = relationship(back_populates="vendor", cascade="all, delete-orphan")
