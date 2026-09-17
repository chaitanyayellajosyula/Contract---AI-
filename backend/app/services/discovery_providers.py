import json
import csv
import io
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse
from urllib import request

class DiscoveryProvider(ABC):
    """Provider contract for bounded, compliant ATS board enumeration."""

    name: str

    @abstractmethod
    def discover(self) -> list[Any]:
        raise NotImplementedError


@dataclass(frozen=True)
class PublicJsonCatalogProvider(DiscoveryProvider):
    """Read a trusted public JSON catalog; never follows candidate URLs."""

    catalog_url: str
    name: str = "public_json_catalog"
    allowed_catalog_hosts: tuple[str, ...] = ()
    timeout: int = 15
    max_bytes: int = 1_000_000

    def __post_init__(self) -> None:
        parsed = urlparse(self.catalog_url)
        if parsed.scheme != "https" or not parsed.hostname:
            raise ValueError("Discovery catalog must use an HTTPS URL")
        if not self.allowed_catalog_hosts or parsed.hostname not in self.allowed_catalog_hosts:
            raise ValueError("Discovery catalog host is not allowlisted")

    def discover(self) -> list[Any]:
        with request.urlopen(self.catalog_url, timeout=self.timeout) as response:
            payload = response.read(self.max_bytes + 1)
        if len(payload) > self.max_bytes:
            raise ValueError("Discovery catalog exceeds the configured size limit")
        parsed = json.loads(payload.decode("utf-8"))
        entries = parsed.get("candidates") if isinstance(parsed, dict) else parsed
        if not isinstance(entries, list):
            raise ValueError("Discovery catalog must contain a candidates list")

        candidates: list[DiscoveryCandidate] = []
        for entry in entries:
            candidate = self._candidate_from_entry(entry)
            if candidate is not None:
                candidates.append(candidate)
        return candidates

    def _candidate_from_entry(self, entry: Any) -> Any | None:
        if not isinstance(entry, dict):
            return None
        source = str(entry.get("source") or "").strip().lower()
        identifier = str(entry.get("identifier") or "").strip()
        jobs_endpoint = str(entry.get("jobs_endpoint") or "").strip()
        if not source or not identifier or not self._is_approved_endpoint(source, jobs_endpoint):
            return None
        from app.services.source_discovery_service import DiscoveryCandidate

        return DiscoveryCandidate(
            source=source,
            identifier=identifier,
            company_name=str(entry.get("company_name") or "").strip() or None,
            source_url=str(entry.get("source_url") or "").strip() or None,
            jobs_endpoint=jobs_endpoint,
            discovery_provider=self.name,
            discovery_key=str(entry.get("discovery_key") or f"{source}:{identifier}"),
            provider_metadata=entry.get("metadata") if isinstance(entry.get("metadata"), dict) else None,
        )

    @staticmethod
    def _is_approved_endpoint(source: str, endpoint: str) -> bool:
        parsed = urlparse(endpoint)
        if parsed.scheme != "https" or not parsed.hostname:
            return False
        approved = {
            "greenhouse": ("boards-api.greenhouse.io", "/v1/boards/"),
            "lever": ("api.lever.co", "/v0/postings/"),
            "ashby": ("api.ashbyhq.com", "/posting-api/job-board/"),
        }
        host_and_path = approved.get(source)
        return host_and_path is not None and parsed.hostname == host_and_path[0] and parsed.path.startswith(host_and_path[1])


@dataclass(frozen=True)
class AtsCompanyCatalogProvider(DiscoveryProvider):
    """Read the verified third-party ATS company directory from its manifest."""

    manifest_url: str
    name: str = "ats_scrapers_company_catalog"
    allowed_hosts: tuple[str, ...] = ("storage.stapply.ai", "raw.githubusercontent.com", "github.com")
    timeout: int = 15
    max_manifest_bytes: int = 1_000_000
    max_csv_bytes: int = 2_000_000
    max_rows_per_ats: int = 25
    supported_ats: tuple[str, ...] = ("greenhouse", "lever", "ashby")

    def __post_init__(self) -> None:
        self._validate_url(self.manifest_url)

    def discover(self) -> list[Any]:
        manifest = self._fetch_json(self.manifest_url, self.max_manifest_bytes)
        directories = manifest.get("by_ats_companies") if isinstance(manifest, dict) else None
        if not isinstance(directories, dict):
            raise ValueError("ATS catalog manifest is missing by_ats_companies")

        candidates: list[Any] = []
        for ats in self.supported_ats:
            entry = directories.get(ats)
            csv_url = entry.get("csv") if isinstance(entry, dict) else None
            if not isinstance(csv_url, str) or not csv_url:
                continue
            self._validate_url(csv_url)
            candidates.extend(self._parse_csv(ats, csv_url))
        return candidates[: self.max_rows_per_ats * len(self.supported_ats)]

    def _parse_csv(self, ats: str, csv_url: str) -> list[Any]:
        from app.services.source_discovery_service import DiscoveryCandidate

        raw = self._fetch_bytes(csv_url, self.max_csv_bytes)
        try:
            rows = csv.DictReader(io.StringIO(raw.decode("utf-8-sig")))
        except UnicodeDecodeError as exc:
            raise ValueError(f"ATS catalog CSV is not UTF-8: {csv_url}") from exc
        candidates: list[DiscoveryCandidate] = []
        seen: set[str] = set()
        for row in rows:
            if len(candidates) >= self.max_rows_per_ats:
                break
            slug = (row.get("slug") or "").strip()
            company_name = (row.get("name") or "").strip()
            source_url = (row.get("url") or "").strip()
            if not slug or not source_url or slug in seen:
                continue
            if not self._is_public_source_url(ats, source_url):
                continue
            seen.add(slug)
            candidates.append(
                DiscoveryCandidate(
                    source=ats,
                    identifier=slug,
                    company_name=company_name or None,
                    source_url=source_url,
                    jobs_endpoint=None,
                    discovery_provider=self.name,
                    discovery_key=f"{ats}:{slug}",
                    provider_metadata={"catalog_url": csv_url},
                )
            )
        return candidates

    def _fetch_json(self, url: str, max_bytes: int) -> dict[str, Any]:
        raw = self._fetch_bytes(url, max_bytes)
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("ATS catalog manifest is not valid JSON") from exc
        if not isinstance(payload, dict):
            raise ValueError("ATS catalog manifest must be a JSON object")
        return payload

    def _fetch_bytes(self, url: str, max_bytes: int) -> bytes:
        with request.urlopen(url, timeout=self.timeout) as response:
            raw = response.read(max_bytes + 1)
        if len(raw) > max_bytes:
            raise ValueError(f"ATS catalog response exceeds {max_bytes} bytes")
        return raw

    def _validate_url(self, url: str) -> None:
        parsed = urlparse(url)
        if parsed.scheme != "https" or parsed.hostname not in self.allowed_hosts:
            raise ValueError(f"ATS catalog URL host is not allowlisted: {url}")

    @staticmethod
    def _is_public_source_url(ats: str, url: str) -> bool:
        parsed = urlparse(url)
        expected_hosts = {
            "greenhouse": {"job-boards.greenhouse.io", "boards.greenhouse.io"},
            "lever": {"jobs.lever.co"},
            "ashby": {"jobs.ashbyhq.com"},
        }
        return parsed.scheme == "https" and parsed.hostname in expected_hosts.get(ats, set())