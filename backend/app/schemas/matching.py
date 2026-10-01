from datetime import datetime
from typing import Literal

from pydantic import BaseModel


MatchStatus = Literal["matched", "gap", "not_assessed"]


class MatchFactor(BaseModel):
    status: MatchStatus
    points: int | None
    max_points: int
    explanation: str


class MatchResponse(BaseModel):
    candidate_id: int
    job_id: int
    overall_score: int | None
    match_level: Literal["strong", "partial", "poor", "limited_evidence", "insufficient_data"]
    evidence_coverage: int
    matched_skills: list[str]
    missing_skills: list[str]
    related_skills: list[str]
    skill_match: MatchFactor
    title_role_match: MatchFactor
    experience_match: MatchFactor
    location_match: MatchFactor
    engagement_authorization_match: MatchFactor
    keyword_domain_match: MatchFactor
    explanation: str
    important_gaps: list[str]
    assessed_at: datetime