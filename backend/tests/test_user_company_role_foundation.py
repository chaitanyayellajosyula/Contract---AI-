import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models.company import Company
from app.models.user import User, UserRole


def test_user_company_relationship_and_valid_roles(tmp_path):
    db_path = tmp_path / "user-company-role-test.db"
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    TestingSessionLocal = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)

    session = TestingSessionLocal()
    try:
        company = Company(name="DW Labs", website="https://dw.example")
        session.add(company)
        session.commit()
        session.refresh(company)

        recruiter = User(
            full_name="Rahul",
            email="rahul@dw.example",
            hashed_password="secret",
            role=UserRole.RECRUITER.value,
            company_id=company.id,
        )
        admin = User(
            full_name="Company Admin",
            email="admin@dw.example",
            hashed_password="secret",
            role=UserRole.COMPANY_ADMIN.value,
            company_id=company.id,
        )
        session.add_all([recruiter, admin])
        session.commit()
        session.refresh(recruiter)
        session.refresh(admin)

        assert recruiter.company_id == company.id
        assert recruiter.company.id == company.id
        assert admin.company.id == company.id
        assert company.users[0].id in {recruiter.id, admin.id}
        assert UserRole.RECRUITER.value == "RECRUITER"
        assert UserRole.COMPANY_ADMIN.value == "COMPANY_ADMIN"

        with pytest.raises(ValueError):
            User(
                full_name="Bad Role",
                email="bad@dw.example",
                hashed_password="secret",
                role="NOT_A_ROLE",
                company_id=company.id,
            )

        with pytest.raises(ValueError):
            User(
                full_name="No Company",
                email="nocompany@dw.example",
                hashed_password="secret",
                role=UserRole.RECRUITER.value,
                company_id=0,
            )
    finally:
        session.close()
        engine.dispose()


def test_auth_and_candidate_privacy_still_work_with_company_role_foundation(tmp_path):
    db_path = tmp_path / "company-role-auth-test.db"
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    TestingSessionLocal = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)

    session = TestingSessionLocal()
    try:
        company = Company(name="Alpha Co", website="https://alpha.example")
        session.add(company)
        session.commit()
        session.refresh(company)

        recruiter = User(
            full_name="Recruiter A",
            email="recruiter-a@example.com",
            hashed_password="secret",
            role=UserRole.RECRUITER.value,
            company_id=company.id,
        )
        session.add(recruiter)
        session.commit()
        session.refresh(recruiter)

        from app.core.auth import get_current_user
        from app.models.candidate import Candidate
        from app.services.auth_service import AuthService

        auth = AuthService(session)
        token = auth.create_access_token(recruiter)
        candidate = Candidate(
            owner_user_id=recruiter.id,
            company_id=company.id,
            first_name="Alice",
            last_name="Test",
            email="alice@test.com",
        )
        session.add(candidate)
        session.commit()

        assert recruiter.company_id == company.id
        assert candidate.owner_user_id == recruiter.id
        assert candidate.company_id == company.id

        # Verify auth still resolves the current user from JWT.
        auth_payload = auth.decode_access_token(token)
        assert auth_payload["sub"] == str(recruiter.id)
    finally:
        session.close()
        engine.dispose()
