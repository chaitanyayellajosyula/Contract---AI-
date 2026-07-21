from typing import Optional

from sqlalchemy.orm import Session

from app.models.user import User


class UserRepository:
    """Repository for user persistence operations."""

    def __init__(self, db: Session):
        self.db = db

    def create_user(self, user: User) -> User:
        """Persist a new user instance and return it."""
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def get_by_email(self, email: str) -> Optional[User]:
        """Return a user matching the provided email address, if present."""
        return self.db.query(User).filter(User.email == email).first()

    def get_by_id(self, user_id: int) -> Optional[User]:
        """Return a user matching the provided identifier, if present."""
        return self.db.get(User, user_id)
