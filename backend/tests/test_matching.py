from fastapi.testclient import TestClient
import pytest

from app.core.database import SessionLocal
from app.main import app
from app.models.candidate import Candidate
from app.models.company import Company
from app.models.job import Job
from app.models.user import User, UserRole
from app.services.auth_service import AuthService
from app.services.matching_service import MatchingService


client = TestClient(app)


def _candidate(**values) -> Candidate:
    return Candidate(
        id=1,
        owner_user_id=1,
        company_id=1,
        first_name="Test",
        last_name="Candidate",
        email="candidate@example.test",
        **values,
    )


def _job(**values) -> Job:
    return Job(id=1, title="Engineer", **values)


@pytest.mark.parametrize(
    ("candidate_values", "job_values", "expected_level", "expected_score"),
    [
        ({"total_experience": "8 years", "current_location": "Austin, TX"}, {"experience": "5+ years", "location": "Austin, TX"}, "limited_evidence", 100),
        ({"total_experience": "3 years", "current_location": "Austin, TX"}, {"experience": "5+ years", "location": "Austin, TX"}, "partial", 43),
        ({"total_experience": "2 years", "current_location": "Boston, MA"}, {"experience": "5+ years", "location": "Austin, TX"}, "poor", 0),
    ],
)
def test_score_uses_only_comparable_fields(candidate_values, job_values, expected_level, expected_score):
    result = MatchingService(None).calculate(_candidate(**candidate_values), _job(**job_values))

    assert result.match_level == expected_level
    assert result.overall_score == expected_score
    assert result.evidence_coverage == 35


def test_missing_candidate_information_is_not_a_match_or_a_failure():
    result = MatchingService(None).calculate(
        _candidate(), _job(experience="5+ years", location="Austin, TX")
    )

    assert result.overall_score is None
    assert result.match_level == "insufficient_data"
    assert result.evidence_coverage == 0
    assert result.experience_match.status == "not_assessed"
    assert result.location_match.status == "not_assessed"


def test_missing_job_requirements_are_not_counted_as_gaps():
    result = MatchingService(None).calculate(
        _candidate(total_experience="8 years", current_location="Austin, TX"), _job()
    )

    assert result.overall_score is None
    assert result.match_level == "insufficient_data"
    assert result.experience_match.status == "not_assessed"
    assert result.location_match.status == "not_assessed"
    assert not any("below" in gap or "does not match" in gap for gap in result.important_gaps)


def test_skills_and_other_unstored_candidate_data_are_never_invented():
    result = MatchingService(None).calculate(
        _candidate(total_experience="8 years"), _job(experience="5+ years", description="Python, AWS")
    )

    assert result.matched_skills == []
    assert result.missing_skills == []
    assert result.related_skills == []
    assert result.skill_match.status == "not_assessed"
    assert result.skill_match.max_points == 35
    assert result.skill_match.points is None
    assert result.title_role_match.status == "not_assessed"
    assert result.keyword_domain_match.status == "not_assessed"
    assert result.engagement_authorization_match.status == "not_assessed"


def test_remote_job_does_not_create_an_assumed_location_match():
    result = MatchingService(None).calculate(
        _candidate(current_location="Austin, TX"),
        _job(location="Remote", remote_type="remote"),
    )

    assert result.location_match.status == "not_assessed"


def test_score_is_repeatable_except_for_assessment_timestamp():
    service = MatchingService(None)
    candidate = _candidate(total_experience="8 years", current_location="Austin, TX")
    job = _job(experience="5+ years", location="Austin, TX")

    first = service.calculate(candidate, job)
    second = service.calculate(candidate, job)

    assert first.model_dump(exclude={"assessed_at"}) == second.model_dump(exclude={"assessed_at"})


def _create_tenant_data():
    db = SessionLocal()
    try:
        company = Company(name="Matching Test Company", website="https://matching-test.example")
        other_company = Company(name="Matching Other Company", website="https://matching-other.example")
        db.add_all([company, other_company])
        db.flush()
        user = User(
            full_name="Matching Recruiter",
            email="matching-recruiter@example.test",
            hashed_password=AuthService(db).hash_password("Password123!"),
            role=UserRole.RECRUITER.value,
            company_id=company.id,
            is_active=True,
        )
        other_user = User(
            full_name="Other Recruiter",
            email="matching-other@example.test",
            hashed_password=AuthService(db).hash_password("Password123!"),
            role=UserRole.RECRUITER.value,
            company_id=other_company.id,
            is_active=True,
        )
        admin = User(
            full_name="Matching Admin",
            email="matching-admin@example.test",
            hashed_password=AuthService(db).hash_password("Password123!"),
            role=UserRole.LEGACY_ADMIN.value,
            is_active=True,
        )
        db.add_all([user, other_user, admin])
        db.flush()
        candidate = Candidate(
            first_name="Match",
            last_name="Candidate",
            email="matching-candidate@example.test",
            owner_user_id=user.id,
            company_id=company.id,
            total_experience="8 years",
            current_location="Austin, TX",
        )
        company_job = Job(title="Matching Company Job", company_id=company.id)
        other_job = Job(title="Matching Other Job", company_id=other_company.id)
        public_job = Job(title="Matching Public Job", location="Austin, TX", experience="5+ years")
        db.add_all([candidate, company_job, other_job, public_job])
        db.commit()
        return {
            "company_id": company.id,
            "user_id": user.id,
            "other_user_id": other_user.id,
            "admin_id": admin.id,
            "candidate_id": candidate.id,
            "company_job_id": company_job.id,
            "other_job_id": other_job.id,
            "public_job_id": public_job.id,
        }
    finally:
        db.close()


def _headers(user_id: int) -> dict[str, str]:
    db = SessionLocal()
    try:
        user = db.get(User, user_id)
        return {"Authorization": f"Bearer {AuthService(db).create_access_token(user)}"}
    finally:
        db.close()


@pytest.fixture
def tenant_data():
    data = _create_tenant_data()
    yield data
    db = SessionLocal()
    try:
        db.query(Candidate).filter(Candidate.email == "matching-candidate@example.test").delete()
        db.query(Job).filter(Job.title.like("Matching %")).delete()
        db.query(User).filter(User.email.like("matching-%@example.test")).delete()
        db.query(Company).filter(Company.name.like("Matching %")).delete()
        db.commit()
    finally:
        db.close()


def test_matching_endpoint_requires_authentication(tenant_data):
    response = client.post(
        f"/matching/candidates/{tenant_data['candidate_id']}/jobs/{tenant_data['public_job_id']}"
    )

    assert response.status_code == 401


def test_matching_endpoint_enforces_candidate_and_job_tenant_access(tenant_data):
    headers = _headers(tenant_data["user_id"])
    candidate_id = tenant_data["candidate_id"]

    allowed = client.post(
        f"/matching/candidates/{candidate_id}/jobs/{tenant_data['company_job_id']}", headers=headers
    )
    cross_tenant_job = client.post(
        f"/matching/candidates/{candidate_id}/jobs/{tenant_data['other_job_id']}", headers=headers
    )
    public_job = client.post(
        f"/matching/candidates/{candidate_id}/jobs/{tenant_data['public_job_id']}", headers=headers
    )

    assert allowed.status_code == 200
    assert cross_tenant_job.status_code == 404
    assert public_job.status_code == 200
    assert "email" not in allowed.json()
    assert "phone" not in allowed.json()


def test_matching_endpoint_rejects_another_recruiters_candidate(tenant_data):
    headers = _headers(tenant_data["other_user_id"])
    response = client.post(
        f"/matching/candidates/{tenant_data['candidate_id']}/jobs/{tenant_data['public_job_id']}",
        headers=headers,
    )

    assert response.status_code == 404


def test_global_admin_can_match_across_companies(tenant_data):
    headers = _headers(tenant_data["admin_id"])
    response = client.post(
        f"/matching/candidates/{tenant_data['candidate_id']}/jobs/{tenant_data['other_job_id']}",
        headers=headers,
    )

    assert response.status_code == 200
