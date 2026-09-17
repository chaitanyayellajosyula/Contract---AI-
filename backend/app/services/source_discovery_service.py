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
from app.services.discovery_providers import DiscoveryProvider

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
    jobs_endpoint: str | None = None
    discovery_provider: str | None = None
    discovery_key: str | None = None
    provider_metadata: dict[str, Any] | None = None


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

    def discover(
        self,
        candidates: list[DiscoveryCandidate],
        providers: list[DiscoveryProvider] | None = None,
        provider_failures: list[dict[str, str]] | None = None,
        duplicate_count: int = 0,
        provider_results: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        candidates = candidates[:MAX_CANDIDATES]
        started_at = datetime.utcnow()
        run = DiscoveryRun(
            started_at=started_at,
            status="running",
            candidates_count=len(candidates),
            providers_count=len(providers or []),
            duplicate_count=duplicate_count,
            failed_provider_count=len(provider_failures or []),
            provider_results=provider_results or provider_failures or None,
        )
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
            run.duration_ms = int((run.completed_at - started_at).total_seconds() * 1000)
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
                "duplicates": duplicate_count,
                "failed_providers": provider_failures or [],
                "provider_results": provider_results or provider_failures or [],
            }
        except Exception as exc:
            run.completed_at = datetime.utcnow()
            run.status = "failed"
            run.message = str(exc)
            self.db.commit()
            raise

    def discover_from_providers(
        self,
        providers: list[DiscoveryProvider],
        explicit_candidates: list[DiscoveryCandidate] | None = None,
    ) -> dict[str, Any]:
        """Enumerate from providers, merge identities, then run final validation."""
        merged: dict[tuple[str, str], DiscoveryCandidate] = {}
        duplicate_count = 0
        provider_failures: list[dict[str, str]] = []
        provider_results: list[dict[str, Any]] = []
        for candidate in explicit_candidates or []:
            merged[(candidate.source.lower(), candidate.identifier)] = candidate
        for provider in providers:
            try:
                candidates = provider.discover()[:MAX_CANDIDATES]
                provider_results.append({"provider": provider.name, "status": "completed", "candidates": len(candidates)})
                for candidate in candidates:
                    key = (candidate.source.lower(), candidate.identifier)
                    if key in merged:
                        duplicate_count += 1
                        merged[key] = self._merge_candidate(merged[key], candidate)
                    else:
                        merged[key] = candidate
            except Exception as exc:
                logger.exception("discovery_provider_failed", extra={"provider": provider.name})
                provider_failures.append({"provider": provider.name, "reason": str(exc)})
                provider_results.append({"provider": provider.name, "status": "failed", "reason": str(exc)})
        return self.discover(
            list(merged.values()),
            providers=providers,
            provider_failures=provider_failures,
            duplicate_count=duplicate_count,
            provider_results=provider_results,
        )

    @staticmethod
    def _merge_candidate(first: DiscoveryCandidate, second: DiscoveryCandidate) -> DiscoveryCandidate:
        providers = []
        for candidate in (first, second):
            if candidate.discovery_provider and candidate.discovery_provider not in providers:
                providers.append(candidate.discovery_provider)
        metadata = dict(first.provider_metadata or first.metadata or {})
        metadata.update(second.provider_metadata or second.metadata or {})
        metadata["providers"] = providers
        return DiscoveryCandidate(
            source=first.source,
            identifier=first.identifier,
            company_name=first.company_name or second.company_name,
            source_url=first.source_url or second.source_url,
            metadata=first.metadata or second.metadata,
            jobs_endpoint=first.jobs_endpoint or second.jobs_endpoint,
            discovery_provider=providers[0] if providers else None,
            discovery_key=first.discovery_key or second.discovery_key,
            provider_metadata=metadata,
        )

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
                jobs_endpoint=candidate.jobs_endpoint or definition[1].format(identifier=identifier),
                source_url=candidate.source_url,
                status="discovered",
                validation_status="pending",
                eligible=False,
                first_discovered_at=now,
                last_checked_at=now,
                metadata_json=candidate.metadata,
                discovery_provider=candidate.discovery_provider,
                discovery_key=candidate.discovery_key or f"{source}:{identifier}",
                last_discovered_at=now,
                provider_metadata=candidate.provider_metadata,
            )
            self.db.add(record)
        else:
            record.last_checked_at = now
            record.company_name = candidate.company_name or record.company_name
            record.source_url = candidate.source_url or record.source_url
            record.metadata_json = candidate.metadata or record.metadata_json
            record.last_discovered_at = now
            record.discovery_provider = candidate.discovery_provider or record.discovery_provider
            record.discovery_key = candidate.discovery_key or record.discovery_key
            record.provider_metadata = candidate.provider_metadata or record.provider_metadata

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
                discovery_provider=candidate.discovery_provider,
                discovery_key=candidate.discovery_key or f"{source}:{identifier}",
                last_discovered_at=now,
                provider_metadata=candidate.provider_metadata,
            )
            self.db.add(record)
        else:
            record.status = "rejected"
            record.validation_status = "invalid"
            record.eligible = False
            record.rejection_reason = reason
            record.last_checked_at = now
        self.db.commit()