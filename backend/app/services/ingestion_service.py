from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.connectors.source_registry import SourceRegistry, source_registry
from app.models.ingestion_run import IngestionRun
from app.services.job_service import JobService


class IngestionService:
    """Coordinates approved source fetching, normalization, and auditing."""

    def __init__(self, db: Session, registry: SourceRegistry = source_registry):
        self.db = db
        self.registry = registry
        self.job_service = JobService(db)

    def ingest(self, source: str, identifier: str) -> dict[str, Any]:
        configuration = self.registry.resolve(source, identifier)
        if configuration is None:
            raise ValueError("Unsupported or disabled job source configuration")

        started_at = datetime.utcnow()
        run = IngestionRun(
            source=configuration.source,
            source_identifier=configuration.identifier,
            started_at=started_at,
            status="running",
        )
        self.db.add(run)
        self.db.commit()
        self.db.refresh(run)

        try:
            connector = configuration.connector_factory(configuration.identifier)
            raw_jobs = connector.fetch()
            normalized_jobs = []
            for raw_job in raw_jobs:
                normalized_jobs.append(connector.normalize_job(raw_job))

            summary = self.job_service.ingest_jobs(
                source=configuration.source,
                normalized_jobs=normalized_jobs,
            )
            completed_at = datetime.utcnow()
            run.completed_at = completed_at
            run.fetched = summary["fetched"]
            run.created = summary["created"]
            run.updated = summary["updated"]
            run.skipped_duplicates = summary["skipped_duplicates"]
            run.rejected = summary["rejected"]
            run.status = "completed"
            self.db.commit()
            return {
                **summary,
                "source_identifier": configuration.identifier,
                "run_id": run.id,
                "started_at": started_at,
                "completed_at": completed_at,
                "status": run.status,
            }
        except Exception as exc:
            run.completed_at = datetime.utcnow()
            run.status = "failed"
            run.message = str(exc)
            self.db.commit()
            raise