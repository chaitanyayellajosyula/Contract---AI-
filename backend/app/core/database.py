from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import declarative_base, sessionmaker

from .config import DATABASE_URL

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def initialize_database() -> None:
    """Create or refresh the development database schema to match the current models."""
    inspector = inspect(engine)
    if inspector.has_table("users"):
        columns = {column["name"] for column in inspector.get_columns("users")}
        expected = {"id", "full_name", "email", "hashed_password", "role", "is_active", "created_at", "updated_at"}
        if columns != expected:
            Base.metadata.drop_all(bind=engine)

    Base.metadata.create_all(bind=engine)
