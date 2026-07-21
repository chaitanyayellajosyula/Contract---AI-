import os
from typing import Optional

from sqlalchemy.orm import Session

from app.models.user import User
from app.services.auth_service import AuthService


DEFAULT_ADMIN_NAME = "Administrator"
DEFAULT_ADMIN_EMAIL = "admin@contracthunter.local"
DEFAULT_ADMIN_PASSWORD = "ChangeMe123!"


def _get_default_admin_values() -> tuple[str, str, str]:
    """Return admin bootstrap values from environment variables or development defaults."""
    name = os.getenv("DEFAULT_ADMIN_NAME", DEFAULT_ADMIN_NAME)
    email = os.getenv("DEFAULT_ADMIN_EMAIL", DEFAULT_ADMIN_EMAIL)
    password = os.getenv("DEFAULT_ADMIN_PASSWORD", DEFAULT_ADMIN_PASSWORD)
    return name, email, password


def bootstrap_admin(db: Session) -> str:
    """Ensure that the application has an administrator account on first startup."""
    existing_admin = db.query(User).filter(User.role == "ADMIN").first()
    if existing_admin is not None:
        print("[bootstrap] Existing admin detected")
        return "existing"

    name, email, password = _get_default_admin_values()
    auth_service = AuthService(db)
    user = User(
        full_name=name,
        email=email,
        hashed_password=auth_service.hash_password(password),
        role="ADMIN",
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    print("[bootstrap] Admin created")
    return "created"
