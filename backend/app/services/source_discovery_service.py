import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable

from sqlalchemy.orm import Session

from app.connectors.ashby.ashby_connector import AshbyConnector
from app.connectors.greenhouse.greenhouse_connector import GreenhouseConnector
from app.connectors.lever.lever_connector import LeverConnector
from app.connectors.source_registry import SourceRegistry, source_registry
from app.models.discovered_source import DiscoveredSource
from app.models.discovery_run import DiscoveryRun

logger = logging.getLogger(__name__)
MAX_CANDIDATES = 25


@dataclass(frozen=True)
class DiscoveryCandidate:
    """Explicit public ATS board candidate supplied by an operator/deployment."""

    source: str
    identifier: str
    company_name: str | None = None
    source_url: str | None = None
    metadata: dict[str, Any] | None = None


_CONNECTORS: dict[str, tuple[type, str]] = {
    "greenhouse": (GreenhouseConnector, "https://boards-api.greenhouse.io/v1/boards/{identifier}/jobs?content=true"),
    "lever": (LeverConnector, "https://api.lever.co/v0/postings/{identifier}?mode=json"),
    "ashby": (AshbyConnector, "https://api.ashbyhq.com/posting-api/job-board/{identifier}"),
}


class SourceDiscoveryService:
    """Validates explicit ATS candidates and promotes only usable public boards."""

    def __init__(
        self,
        db: Session,
        registry: SourceRegistry = source_registry,
        connector_factories: dict[str, Callable[[str], Any]] | None = None,
    ) -> None:
        self.db = db
        self.registry = registry
        self.connector_factories = connector_factories or {
            name: connector for name, (connector, _template) in _CONNECTORS.items()
        }

    def discover(self, candidates: list[DiscoveryCandidate]) -> dict[str, Any]:
        candidates = candidates[:MAX_CANDIDATES]
        started_at = datetime.utcnow()
        run = DiscoveryRun(started_at=started_at, status="running", candidates_count=len(candidates))
        self.db.add(run)
        self.db.commit()
        discovered = validated = rejected = 0
        reasons: list[dict[str, str]] = []
        try:
            for candidate in candidates:
                result = self._process_candidate(candidate)
                discovered += 1
                if result["validated"]:
                    validated += 1
                else:
                    rejected += 1
                    reasons.append({"source": candidate.source, "identifier": candidate.identifier, "reason": result["reason"]})
            run.completed_at = datetime.utcnow()
            run.discovered_count = discovered
            run.validated_count = validated
            run.rejected_count = rejected
            run.status = "completed"
            self.db.commit()
            return {
                "run_id": run.id,
                "status": run.status,
                "candidates": len(candidates),
                "discovered": discovered,
                "validated": validated,
                "rejected": rejected,
                "rejection_reasons": reasons,
            }
        except Exception as exc:
            run.completed_at = datetime.utcnow()
            run.status = "failed"
            run.message = str(exc)
            self.db.commit()
            raise

    def _process_candidate(self, candidate: DiscoveryCandidate) -> dict[str, Any]:
        source = candidate.source.strip().lower()
        identifier = candidate.identifier.strip()
        definition = _CONNECTORS.get(source)
        now = datetime.utcnow()
        record = self.db.query(DiscoveredSource).filter(
            DiscoveredSource.source == source,
            DiscoveredSource.identifier == identifier,
        ).first()
        if record is None:
            if not identifier or definition is None:
                reason = "Unsupported ATS type or missing board identifier"
                self._record_rejection(record, candidate, source, identifier, now, reason)
                return {"validated": False, "reason": reason}
            record = DiscoveredSource(
                source=source,
                identifier=identifier,
                company_name=candidate.company_name,
                jobs_endpoint=definition[1].format(identifier=identifier),
                source_url=candidate.source_url,
                status="discovered",
                validation_status="pending",
                eligible=False,
                first_discovered_at=now,
                last_checked_at=now,
                metadata_json=candidate.metadata,
            )
            self.db.add(record)
        else:
            record.last_checked_at = now
            record.company_name = candidate.company_name or record.company_name
            record.source_url = candidate.source_url or record.source_url
            record.metadata_json = candidate.metadata or record.metadata_json

        try:
            connector = self.connector_factories[source](identifier)
            jobs = connector.fetch()
            if not isinstance(jobs, list):
                raise ValueError("Public endpoint did not return a jobs list")
        except Exception as exc:
            reason = f"Public endpoint validation failed: {exc}"
            self._record_rejection(record, candidate, source, identifier, now, reason)
            return {"validated": False, "reason": reason}

        record.status = "validated"
        record.validation_status = "valid"
        record.eligible = True
        record.last_validated_at = now
        record.rejection_reason = None
        self.registry.register_discovered(source, identifier)
        self.db.commit()
        logger.info("source_discovered", extra={"source": source, "identifier": identifier})
        return {"validated": True, "reason": ""}

    def _record_rejection(self, record, candidate, source, identifier, now, reason: str) -> None:
        if record is None:
            definition = _CONNECTORS.get(source)
            record = DiscoveredSource(
                source=source or "unknown",
                identifier=identifier or "unknown",
                company_name=candidate.company_name,
                jobs_endpoint=definition[1].format(identifier=identifier) if definition else "",
                source_url=candidate.source_url,
                status="rejected",
                validation_status="invalid",
                eligible=False,
                first_discovered_at=now,
                last_checked_at=now,
                rejection_reason=reason,
                metadata_json=candidate.metadata,
            )
            self.db.add(record)
        else:
            record.status = "rejected"
            record.validation_status = "invalid"
            record.eligible = False
            record.rejection_reason = reason
            record.last_checked_at = now
        self.db.commit()