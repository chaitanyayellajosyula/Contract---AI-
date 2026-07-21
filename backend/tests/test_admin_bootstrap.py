from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.core.bootstrap import bootstrap_admin
from app.models.user import User


def test_bootstrap_creates_first_admin_and_prevents_duplicates(tmp_path):
    db_path = tmp_path / "bootstrap-test.db"
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    TestingSessionLocal = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)

    session = TestingSessionLocal()
    try:
        first_result = bootstrap_admin(session)
        assert first_result == "created"

        admins = session.query(User).filter(User.role == "ADMIN").all()
        assert len(admins) == 1
        assert admins[0].email == "admin@contracthunter.local"

        second_result = bootstrap_admin(session)
        assert second_result == "existing"
    finally:
        session.close()
        engine.dispose()
