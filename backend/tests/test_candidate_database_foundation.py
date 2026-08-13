from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models import Candidate, Company, User
from app.repositories.candidate_repository import CandidateRepository


def test_candidate_models_repository_and_metadata_work_with_sqlite(tmp_path):
    db_path = tmp_path / "candidate-foundation-test.db"
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    TestingSessionLocal = sessionmaker(bind=engine)
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    session = TestingSessionLocal()
    try:
        user = User(full_name="Jane Recruiter", email="jane@example.com", hashed_password="secret")
        company = Company(name="Acme Labs", website="https://acme.example")
        session.add_all([user, company])
        session.commit()
        session.refresh(user)
        session.refresh(company)

        repo = CandidateRepository(session)
        candidate = Candidate(
            owner_user_id=user.id,
            company_id=company.id,
            first_name="Alice",
            last_name="Johnson",
            email="alice@example.com",
            phone="555-0101",
            linkedin_url="https://linkedin.com/in/alice",
            current_location="New York, NY",
            preferred_location="Remote",
            visa_status="H1B",
            total_experience="8 years",
            us_experience="6 years",
            current_rate="$120/hr",
            expected_rate="$130/hr",
            availability_status="Available",
            resume_filename="alice_resume.pdf",
        )

        created = repo.create_candidate(candidate)
        assert created.id is not None
        assert repo.get_candidate(created.id).first_name == "Alice"
        assert len(repo.list_candidates()) == 1

        updated = repo.update_candidate(created.id, {"last_name": "Smith", "availability_status": "Open to offers"})
        assert updated is not None
        assert updated.last_name == "Smith"
        assert updated.availability_status == "Open to offers"

        assert repo.delete_candidate(created.id) is True
        assert repo.get_candidate(created.id) is None

        session.add_all([
            User(full_name="Another Recruiter", email="another@example.com", hashed_password="secret"),
            Company(name="Beta Systems", website="https://beta.example"),
        ])
        session.commit()

        new_user = session.query(User).filter(User.email == "another@example.com").one()
        new_company = session.query(Company).filter(Company.name == "Beta Systems").one()

        candidate_2 = Candidate(
            owner_user_id=new_user.id,
            company_id=new_company.id,
            first_name="Bob",
            last_name="Brown",
            email="bob@example.com",
            availability_status="Interviewing",
        )
        session.add(candidate_2)
        session.commit()
        session.refresh(candidate_2)

        assert candidate_2.owner == new_user
        assert candidate_2.company == new_company
        assert new_user.candidates[-1].id == candidate_2.id
        assert new_company.candidates[-1].id == candidate_2.id

        assert "candidates" in Base.metadata.tables
    finally:
        session.close()
        engine.dispose()
