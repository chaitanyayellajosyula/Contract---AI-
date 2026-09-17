import json
from datetime import datetime, timezone
from typing import Any
from urllib import request

from app.connectors.base.base_connector import BaseConnector
from app.services.job_classification import classify_engagement


class GreenhouseConnector(BaseConnector):
    """Greenhouse public jobs connector for a single board."""

    API_BASE = "https://boards-api.greenhouse.io/v1/boards"

    def __init__(self, board: str, timeout_seconds: int = 30):
        if not board or not board.strip():
            raise ValueError("Greenhouse board is required")
        self.board = board
        self.timeout_seconds = timeout_seconds

    def connect(self) -> None:
        return None

    def fetch(self) -> list[dict[str, Any]]:
        if self.timeout_seconds == 30:
            return self.fetch_jobs(self.board)
        return self.fetch_jobs(self.board, timeout=self.timeout_seconds)

    @classmethod
    def fetch_jobs(cls, board: str, timeout: int = 30) -> list[dict[str, Any]]:
        if not board or not board.strip():
            raise ValueError("Greenhouse board is required")
        url = f"{cls.API_BASE}/{board}/jobs?content=true"
        with request.urlopen(url, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
        jobs = payload.get("jobs") or []
        return jobs if isinstance(jobs, list) else []

    @staticmethod
    def _normalize_employment_type(raw: Any) -> str | None:
        if not raw:
            return None
        if isinstance(raw, str):
            return raw.strip() or None
        if isinstance(raw, dict):
            value = raw.get("name") or raw.get("value")
            return str(value).strip() or None if value is not None else None
        return str(raw).strip() or None

    @staticmethod
    def normalize_job(raw_job: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(raw_job, dict):
            raise ValueError("Job payload must be a dictionary")

        title = str(raw_job.get("title") or "").strip()
        if not title:
            raise ValueError("Job title is required")

        description = raw_job.get("content") or ""
        location = raw_job.get("location")
        location_name = location.get("name") if isinstance(location, dict) else None
        absolute_url = raw_job.get("absolute_url")
        first_published = raw_job.get("first_published")
        source_job_id = str(raw_job.get("id") or "").strip()

        if not source_job_id:
            raise ValueError("Greenhouse job id is required")

        employment_type = None
        if isinstance(raw_job.get("employment_type"), dict):
            employment_type = classify_engagement(raw_job["employment_type"].get("name") or raw_job["employment_type"].get("value"))
        elif raw_job.get("employment_type"):
            employment_type = classify_engagement(raw_job.get("employment_type"))

        remote_type = "remote" if isinstance(location_name, str) and "remote" in location_name.lower() else None
        posted_at = None
        if isinstance(first_published, str):
            try:
                posted_at = datetime.fromisoformat(first_published.replace("Z", "+00:00"))
                if posted_at.tzinfo is not None:
                    posted_at = posted_at.astimezone(timezone.utc).replace(tzinfo=None)
            except ValueError:
                posted_at = None

        normalized = {
            "title": title,
            "description": description or None,
            "location": location_name or None,
            "employment_type": employment_type,
            "remote_type": remote_type,
            "status": "active",
            "source": "greenhouse",
            "source_job_id": source_job_id,
            "source_url": absolute_url or None,
            "apply_url": absolute_url or None,
            "source_updated_at": posted_at,
            "source_company": None,
            "source_metadata": None,
            "posted_at": posted_at,
            "expires_at": None,
            "viewed": False,
            "bookmarked": False,
            "company_id": None,
            "recruiter_id": None,
        }
        return normalized

    def close(self) -> None:
        return None
