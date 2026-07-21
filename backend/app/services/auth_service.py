from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.core.config import ACCESS_TOKEN_EXPIRE_MINUTES, ALGORITHM, SECRET_KEY
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.schemas.user import UserCreate, UserLogin

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class AuthService:
    """Service layer containing authentication business logic."""

    def __init__(self, db: Session):
        self.repository = UserRepository(db)

    def register_user(self, data: UserCreate) -> User:
        """Create a new user with a hashed password."""
        if self.repository.get_by_email(data.email):
            raise ValueError("Email already registered")

        user = User(
            full_name=data.full_name,
            email=data.email,
            hashed_password=self.hash_password(data.password),
            role="member",
            is_active=True,
        )
        return self.repository.create_user(user)

    def authenticate_user(self, data: UserLogin) -> Optional[User]:
        """Validate a user login attempt and return the matching account."""
        user = self.repository.get_by_email(data.email)
        if not user or not self.verify_password(data.password, user.hashed_password):
            return None
        return user

    def create_access_token(self, user: User) -> str:
        """Create a signed JWT access token for a user."""
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        payload = {"sub": str(user.id), "exp": expire, "role": user.role}
        return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

    def decode_access_token(self, token: str) -> dict:
        """Decode and validate a JWT access token."""
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])

    def hash_password(self, password: str) -> str:
        """Hash a plaintext password using bcrypt."""
        safe_password = password[:72]
        return pwd_context.hash(safe_password)

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify a plaintext password against a stored bcrypt hash."""
        safe_password = plain_password[:72]
        return pwd_context.verify(safe_password, hashed_password)
