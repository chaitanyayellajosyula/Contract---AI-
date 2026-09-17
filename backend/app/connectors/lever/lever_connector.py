import json
from datetime import datetime, timezone
from typing import Any
from urllib import request

from app.connectors.base.base_connector import BaseConnector


class LeverConnector(BaseConnector):
    """Lever's unauthenticated public postings endpoint for one site."""

    API_BASE = "https://api.lever.co/v0/postings"

    def __init__(self, site: str):
        if not site or not site.strip():
            raise ValueError("Lever site is required")
        self.site = site.strip()

    def connect(self) -> None:
        return None

    def fetch(self) -> list[dict[str, Any]]:
        return self.fetch_jobs(self.site)

    @classmethod
    def fetch_jobs(cls, site: str) -> list[dict[str, Any]]:
        if not site or not site.strip():
            raise ValueError("Lever site is required")
        url = f"{cls.API_BASE}/{site.strip()}?mode=json"
        with request.urlopen(url, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))
        return payload if isinstance(payload, list) else []

    @staticmethod
    def _normalize_timestamp(raw: Any) -> datetime | None:
        if raw is None:
            return None
        try:
            timestamp = float(raw)
        except (TypeError, ValueError):
            return None
        return datetime.fromtimestamp(timestamp / 1000, tz=timezone.utc).replace(tzinfo=None)

    @staticmethod
    def normalize_job(raw_job: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(raw_job, dict):
            raise ValueError("Job payload must be a dictionary")

        title = str(raw_job.get("text") or "").strip()
        source_job_id = str(raw_job.get("id") or "").strip()
        source_url = str(raw_job.get("hostedUrl") or raw_job.get("applyUrl") or "").strip()
        if not title:
            raise ValueError("Lever job title is required")
        if not source_job_id:
            raise ValueError("Lever job id is required")
        if not source_url:
            raise ValueError("Lever job URL is required")

        categories = raw_job.get("categories") or {}
        if not isinstance(categories, dict):
            categories = {}
        location = categories.get("location")
        commitment = categories.get("commitment")
        workplace_type = raw_job.get("workplaceType")
        location_text = str(location).strip() if location is not None else None
        remote_value = " ".join(str(value) for value in (location, workplace_type) if value)
        remote_type = "remote" if "remote" in remote_value.lower() else None

        return {
            "title": title,
            "description": raw_job.get("descriptionPlain") or raw_job.get("description") or None,
            "location": location_text,
            "employment_type": str(commitment).strip() if commitment else None,
            "remote_type": remote_type,
            "status": "active",
            "source": "lever",
            "source_job_id": source_job_id,
            "source_url": source_url,
            "posted_at": LeverConnector._normalize_timestamp(raw_job.get("createdAt")),
            "expires_at": None,
            "viewed": False,
            "bookmarked": False,
            "company_id": None,
            "recruiter_id": None,
        }

    def close(self) -> None:
        return None