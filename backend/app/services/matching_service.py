import re
from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.candidate import Candidate
from app.models.job import Job
from app.models.user import User, UserRole
from app.schemas.matching import MatchFactor, MatchResponse
from app.services.candidate_service import CandidateService
from app.services.submission_service import SubmissionService


_WEIGHTS = {
    "skill_match": 35,
    "title_role_match": 15,
    "experience_match": 20,
    "location_match": 15,
    "engagement_authorization_match": 10,
    "keyword_domain_match": 5,
}
_YEARS = re.compile(r"(\d+(?:\.\d+)?)\s*(?:\+\s*)?(?:years?|yrs?)\b", re.IGNORECASE)


class MatchingService:
    """Calculate a reproducible match from candidate and job fields already stored."""

    def __init__(self, db: Session):
        self.db = db

    def match_for_user(self, candidate_id: int, job_id: int, user: User) -> MatchResponse:
        candidate = self.db.get(Candidate, candidate_id)
        job = self.db.get(Job, job_id)
        if candidate is None or job is None or not self._can_match(user, candidate, job):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidate or job not found")
        return self.calculate(candidate, job)

    def calculate(self, candidate: Candidate, job: Job) -> MatchResponse:
        factors = {
            "skill_match": self._unassessed("Candidate skills and structured job skill requirements are not stored.", _WEIGHTS["skill_match"]),
            "title_role_match": self._unassessed("Candidate role or title is not stored.", _WEIGHTS["title_role_match"]),
            "experience_match": self._experience(candidate.total_experience, job.experience),
            "location_match": self._location(candidate, job),
            "engagement_authorization_match": self._unassessed(
                "The stored candidate availability and visa fields cannot be compared to a structured job requirement.",
                _WEIGHTS["engagement_authorization_match"],
            ),
            "keyword_domain_match": self._unassessed(
                "Candidate skill or domain keywords are not stored; job description text is not treated as candidate evidence.",
                _WEIGHTS["keyword_domain_match"],
            ),
        }
        assessed_weight = sum(
            _WEIGHTS[name]
            for name, factor in factors.items()
            if factor.status != "not_assessed"
        )
        earned_points = sum(
            factor.points or 0
            for factor in factors.values()
            if factor.status != "not_assessed"
        )
        score = round(earned_points / assessed_weight * 100) if assessed_weight else None
        coverage = round(assessed_weight / sum(_WEIGHTS.values()) * 100)
        level = self._match_level(score, coverage)
        gaps = [
            factor.explanation
            for factor in factors.values()
            if factor.status == "gap"
        ]
        gaps.extend(
            f"Not assessed: {factor.explanation}"
            for factor in factors.values()
            if factor.status == "not_assessed"
        )
        assessed_names = [
            name.replace("_match", "").replace("_", " ")
            for name, factor in factors.items()
            if factor.status != "not_assessed"
        ]
        if score is None:
            explanation = "No candidate/job requirements could be compared using the fields currently stored."
        else:
            explanation = (
                f"Evidence score {score}/100 across {', '.join(assessed_names)}; "
                f"{coverage}% of the weighted matching criteria could be assessed. "
                "The score is not a probability and unassessed criteria do not count as matches."
            )

        return MatchResponse(
            candidate_id=candidate.id,
            job_id=job.id,
            overall_score=score,
            match_level=level,
            evidence_coverage=coverage,
            matched_skills=[],
            missing_skills=[],
            related_skills=[],
            **factors,
            explanation=explanation,
            important_gaps=gaps,
            assessed_at=datetime.utcnow(),
        )

    def _can_match(self, user: User, candidate: Candidate, job: Job) -> bool:
        if user.role == UserRole.LEGACY_ADMIN.value:
            return True

        authorized_candidate = CandidateService(self.db).get_candidate_for_user(candidate.id, user)
        if authorized_candidate is None or user.company_id != candidate.company_id:
            return False
        if user.role not in {UserRole.RECRUITER.value, UserRole.COMPANY_ADMIN.value}:
            return False

        job_company_id = SubmissionService._job_company_id(job)
        return job_company_id is None or job_company_id == user.company_id

    @staticmethod
    def _unassessed(explanation: str, max_points: int = 0) -> MatchFactor:
        return MatchFactor(status="not_assessed", points=None, max_points=max_points, explanation=explanation)

    @staticmethod
    def _experience(candidate_value: str | None, job_value: str | None) -> MatchFactor:
        if not candidate_value:
            return MatchingService._unassessed("Candidate experience is not recorded.", _WEIGHTS["experience_match"])
        if not job_value:
            return MatchingService._unassessed("The job has no recorded experience requirement.", _WEIGHTS["experience_match"])
        candidate_years = _YEARS.search(candidate_value)
        required_years = _YEARS.search(job_value)
        if candidate_years is None or required_years is None:
            return MatchingService._unassessed(
                "Experience could not be compared because it is not expressed in years.",
                _WEIGHTS["experience_match"],
            )
        meets_requirement = float(candidate_years.group(1)) >= float(required_years.group(1))
        if meets_requirement:
            return MatchFactor(
                status="matched",
                points=_WEIGHTS["experience_match"],
                max_points=_WEIGHTS["experience_match"],
                explanation=f"Recorded experience ({candidate_value}) meets the job requirement ({job_value}).",
            )
        return MatchFactor(
            status="gap",
            points=0,
            max_points=_WEIGHTS["experience_match"],
            explanation=f"Recorded experience ({candidate_value}) is below the job requirement ({job_value}).",
        )

    @staticmethod
    def _location(candidate: Candidate, job: Job) -> MatchFactor:
        candidate_locations = {
            value.strip().casefold()
            for value in (candidate.current_location, candidate.preferred_location)
            if value and value.strip()
        }
        if not candidate_locations:
            return MatchingService._unassessed("Candidate location and location preference are not recorded.", _WEIGHTS["location_match"])
        if not job.location:
            return MatchingService._unassessed("The job has no recorded location requirement.", _WEIGHTS["location_match"])
        if job.remote_type and "remote" in job.remote_type.casefold():
            return MatchingService._unassessed(
                "The job is marked remote, so no location comparison was scored.",
                _WEIGHTS["location_match"],
            )
        job_location = job.location.strip().casefold()
        if job_location in candidate_locations:
            return MatchFactor(
                status="matched",
                points=_WEIGHTS["location_match"],
                max_points=_WEIGHTS["location_match"],
                explanation=f"Candidate location matches the job location ({job.location}).",
            )
        recorded = ", ".join(sorted(candidate_locations))
        return MatchFactor(
            status="gap",
            points=0,
            max_points=_WEIGHTS["location_match"],
            explanation=f"Recorded candidate location ({recorded}) does not match the job location ({job.location}).",
        )

    @staticmethod
    def _match_level(score: int | None, coverage: int) -> str:
        if score is None:
            return "insufficient_data"
        if coverage < 60:
            if score >= 75:
                return "limited_evidence"
            if score >= 40:
                return "partial"
            return "poor"
        if score >= 75:
            return "strong"
        if score >= 40:
            return "partial"
        return "poor"