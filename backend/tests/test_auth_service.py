from app.services.auth_service import AuthService


def test_password_hashing_and_verification_round_trip():
    service = AuthService(db=None)  # type: ignore[arg-type]
    password = "short123"

    hashed = service.hash_password(password)
    assert hashed.startswith("$2")
    assert service.verify_password(password, hashed) is True
    assert service.verify_password("wrong", hashed) is False
