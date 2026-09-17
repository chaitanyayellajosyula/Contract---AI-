from datetime import datetime

from sqlalchemy import Boolean, DateTime, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class DiscoveredSource(Base):
    """Persisted record of a public ATS board discovered and validated."""

    __tablename__ = "discovered_sources"
    __table_args__ = (UniqueConstraint("source", "identifier", name="uq_discovered_sources_source_identifier"),)

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    source: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    identifier: Mapped[str] = mapped_column(String(255), nullable=False)
    company_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    jobs_endpoint: Mapped[str] = mapped_column(String(1000), nullable=False)
    source_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="discovered")
    validation_status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending")
    eligible: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    first_discovered_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    last_checked_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    last_validated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    discovery_provider: Mapped[str | None] = mapped_column(String(100), nullable=True)
    discovery_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    last_discovered_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    provider_metadata: Mapped[dict | None] = mapped_column(JSON, nullable=True)