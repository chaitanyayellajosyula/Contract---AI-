import json
from datetime import datetime, timezone
from typing import Any
from urllib import request

from app.connectors.base.base_connector import BaseConnector
from app.services.job_classification import classify_engagement


class AshbyConnector(BaseConnector):
    """Ashby's unauthenticated public job-board API for one board slug."""

    API_BASE = "https://api.ashbyhq.com/posting-api/job-board"

    def __init__(self, board: str, timeout_seconds: int = 30):
        if not board or not board.strip():
            raise ValueError("Ashby board is required")
        self.board = board.strip()
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
            raise ValueError("Ashby board is required")
        url = f"{cls.API_BASE}/{board.strip()}"
        with request.urlopen(url, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
        jobs = payload.get("jobs") if isinstance(payload, dict) else None
        return jobs if isinstance(jobs, list) else []

    @staticmethod
    def _normalize_timestamp(raw: Any) -> datetime | None:
        if not isinstance(raw, str) or not raw.strip():
            return None
        try:
            timestamp = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            return None
        if timestamp.tzinfo is not None:
            timestamp = timestamp.astimezone(timezone.utc).replace(tzinfo=None)
        return timestamp

    @staticmethod
    def normalize_job(raw_job: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(raw_job, dict):
            raise ValueError("Job payload must be a dictionary")

        title = str(raw_job.get("title") or "").strip()
        source_job_id = str(raw_job.get("id") or "").strip()
        source_url = str(raw_job.get("jobUrl") or "").strip()
        apply_url = str(raw_job.get("applyUrl") or "").strip() or None
        if not title:
            raise ValueError("Ashby job title is required")
        if not source_job_id:
            raise ValueError("Ashby job id is required")
        if not source_url:
            raise ValueError("Ashby job URL is required")

        location = str(raw_job.get("location") or "").strip() or None
        workplace_type = str(raw_job.get("workplaceType") or "").strip() or None
        remote_type = workplace_type.lower() if workplace_type else None
        if remote_type not in {"remote", "hybrid", "on-site"}:
            remote_type = "remote" if raw_job.get("isRemote") is True else None

        metadata = {
            key: raw_job[key]
            for key in ("department", "team", "secondaryLocations")
            if raw_job.get(key) is not None
        }
        return {
            "title": title,
            "description": raw_job.get("descriptionHtml") or None,
            "location": location,
            "employment_type": classify_engagement(raw_job.get("employmentType")),
            "remote_type": remote_type,
            "status": "active",
            "source": "ashby",
            "source_job_id": source_job_id,
            "source_url": source_url,
            "apply_url": apply_url,
            "source_updated_at": AshbyConnector._normalize_timestamp(raw_job.get("publishedAt")),
            "source_company": raw_job.get("companyName") or None,
            "source_metadata": metadata or None,
            "posted_at": AshbyConnector._normalize_timestamp(raw_job.get("publishedAt")),
            "expires_at": None,
            "viewed": False,
            "bookmarked": False,
            "company_id": None,
            "recruiter_id": None,
        }

    def close(self) -> None:
        return None