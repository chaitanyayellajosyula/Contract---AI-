from datetime import datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models import Company, Job, Recruiter, Vendor
from app.repositories.job_repository import JobRepository


def test_job_models_and_repository_work_with_sqlite(tmp_path):
    db_path = tmp_path / "jobs-foundation-test.db"
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    TestingSessionLocal = sessionmaker(bind=engine)
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    session = TestingSessionLocal()
    try:
        company = Company(name="Acme Corp", website="https://acme.example")
        session.add(company)
        session.commit()
        session.refresh(company)

        vendor = Vendor(name="Acme Staffing", email="staffing@acme.example", phone="555-0100", company_id=company.id)
        session.add(vendor)
        session.commit()
        session.refresh(vendor)

        recruiter = Recruiter(full_name="Ada Lovelace", email="ada@acme.example", phone="555-0101", vendor_id=vendor.id)
        session.add(recruiter)
        session.commit()
        session.refresh(recruiter)

        repo = JobRepository(session)
        job = Job(
            title="Senior Python Engineer",
            description="Build resilient integrations",
            location="Remote",
            employment_type="full_time",
            experience="senior",
            salary="180000",
            remote_type="remote",
            status="active",
            source="manual",
            source_job_id="job-001",
            posted_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(days=30),
            viewed=False,
            bookmarked=False,
            recruiter_id=recruiter.id,
        )

        created_job = repo.create(job)
        assert created_job.id is not None
        assert repo.get(created_job.id).title == "Senior Python Engineer"
        assert len(repo.get_all()) == 1

        updated_job = repo.update(created_job.id, {"title": "Principal Python Engineer", "status": "review"})
        assert updated_job is not None
        assert updated_job.title == "Principal Python Engineer"
        assert updated_job.status == "review"

        assert repo.delete(created_job.id) is True
        assert repo.get(created_job.id) is None
    finally:
        session.close()
        engine.dispose()
