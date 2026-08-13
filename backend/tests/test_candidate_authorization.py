"""Test suite for candidate authorization and role-based access control.

Tests verify that:
- RECRUITERs can only see/modify their own candidates
- COMPANY_ADMINs can see/modify all candidates in their company
- Cross-company access is forbidden (returns 404)
- Ownership and company fields cannot be modified via PATCH
- Candidates can only be created with the authenticated user's company
"""

import pytest
from fastapi.testclient import TestClient

from app.core.database import SessionLocal
from app.main import app
from app.models.candidate import Candidate
from app.models.company import Company
from app.models.user import User, UserRole
from app.services.auth_service import AuthService

client = TestClient(app)


def _create_user(
    email: str,
    full_name: str,
    role: str = UserRole.RECRUITER.value,
    company: Company | None = None,
) -> User:
    """Create or retrieve a user for testing."""
    db = SessionLocal()
    try:
        existing = db.query(User).filter(User.email == email).first()
        if existing is not None:
            return existing

        user = User(
            full_name=full_name,
            email=email,
            hashed_password=AuthService(db).hash_password("Password123!"),
            role=role,
            company_id=company.id if company else None,
            is_active=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user
    finally:
        db.close()


def _auth_headers_for(email: str) -> dict[str, str]:
    """Get authorization headers for a user."""
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        if user is None:
            raise RuntimeError(f"User {email} not found")
        token = AuthService(db).create_access_token(user)
        return {"Authorization": f"Bearer {token}"}
    finally:
        db.close()


def _create_company(name: str) -> Company:
    """Create a test company."""
    db = SessionLocal()
    try:
        company = Company(
            name=name,
            website=f"https://{name.lower().replace(' ', '')}.example.com",
        )
        db.add(company)
        db.commit()
        db.refresh(company)
        return company
    finally:
        db.close()


def _create_candidate(
    first_name: str,
    last_name: str,
    email: str,
    owner: User,
    company: Company,
) -> Candidate:
    """Create a candidate directly in the database."""
    db = SessionLocal()
    try:
        candidate = Candidate(
            first_name=first_name,
            last_name=last_name,
            email=email,
            owner_user_id=owner.id,
            company_id=company.id,
        )
        db.add(candidate)
        db.commit()
        db.refresh(candidate)
        return candidate
    finally:
        db.close()


def _cleanup():
    """Clean up test data."""
    db = SessionLocal()
    try:
        # Delete in dependency order
        db.query(Candidate).delete()
        db.query(User).filter(User.email.like("%@example.com")).delete()
        db.query(Company).delete()
        db.commit()
    finally:
        db.close()


@pytest.fixture(autouse=True)
def setup_teardown():
    """Setup and teardown for each test."""
    _cleanup()
    yield
    _cleanup()


# ============================================================================
# RECRUITER TESTS
# ============================================================================


def test_recruiter_can_create_candidate():
    """Test that a recruiter can create a candidate."""
    company_a = _create_company("DW Labs")
    recruiter_a = _create_user("rahul@example.com", "Rahul", company=company_a)
    headers = _auth_headers_for("rahul@example.com")

    response = client.post(
        "/candidates",
        json={
            "first_name": "Alice",
            "last_name": "Developer",
            "email": "alice@example.com",
            "phone": "555-0001",
        },
        headers=headers,
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["owner_user_id"] == recruiter_a.id
    assert payload["company_id"] == company_a.id
    assert payload["email"] == "alice@example.com"


def test_recruiter_cannot_override_owner_during_creation():
    """Test that a recruiter cannot set owner_user_id during creation."""
    company_a = _create_company("DW Labs")
    recruiter_a = _create_user("rahul@example.com", "Rahul", company=company_a)
    recruiter_b = _create_user("priya@example.com", "Priya", company=company_a)
    headers = _auth_headers_for("rahul@example.com")

    # Attempt to set owner_user_id to another user
    response = client.post(
        "/candidates",
        json={
            "first_name": "Bob",
            "last_name": "Builder",
            "email": "bob@example.com",
            "owner_user_id": recruiter_b.id,
        },
        headers=headers,
    )

    assert response.status_code == 201
    payload = response.json()
    # Should be owned by rahul, not priya
    assert payload["owner_user_id"] == recruiter_a.id


def test_recruiter_cannot_override_company_during_creation():
    """Test that a recruiter cannot set company_id during creation."""
    company_a = _create_company("DW Labs")
    company_b = _create_company("Company B")
    recruiter_a = _create_user("rahul@example.com", "Rahul", company=company_a)
    headers = _auth_headers_for("rahul@example.com")

    # Attempt to set company_id to another company
    response = client.post(
        "/candidates",
        json={
            "first_name": "Charlie",
            "last_name": "Corporate",
            "email": "charlie@example.com",
            "company_id": company_b.id,
        },
        headers=headers,
    )

    assert response.status_code == 201
    payload = response.json()
    # Should be in company_a, not company_b
    assert payload["company_id"] == company_a.id


def test_recruiter_sees_only_own_candidates():
    """Test that a recruiter only sees their own candidates (GET list)."""
    company_a = _create_company("DW Labs")
    recruiter_a = _create_user("rahul@example.com", "Rahul", company=company_a)
    recruiter_b = _create_user("priya@example.com", "Priya", company=company_a)

    candidate_a1 = _create_candidate("Alice", "A", "alice@example.com", recruiter_a, company_a)
    candidate_a2 = _create_candidate("Bob", "B", "bob@example.com", recruiter_a, company_a)
    candidate_a3 = _create_candidate("Charlie", "C", "charlie@example.com", recruiter_b, company_a)

    headers_a = _auth_headers_for("rahul@example.com")
    response = client.get("/candidates", headers=headers_a)

    assert response.status_code == 200
    candidates = response.json()
    assert len(candidates) == 2
    ids = {c["id"] for c in candidates}
    assert candidate_a1.id in ids
    assert candidate_a2.id in ids
    assert candidate_a3.id not in ids


def test_recruiter_gets_404_for_other_recruiter_candidate():
    """Test that a recruiter gets 404 for another recruiter's candidate."""
    company_a = _create_company("DW Labs")
    recruiter_a = _create_user("rahul@example.com", "Rahul", company=company_a)
    recruiter_b = _create_user("priya@example.com", "Priya", company=company_a)

    candidate_b = _create_candidate("David", "D", "david@example.com", recruiter_b, company_a)

    headers_a = _auth_headers_for("rahul@example.com")
    response = client.get(f"/candidates/{candidate_b.id}", headers=headers_a)

    assert response.status_code == 404


def test_recruiter_cannot_patch_other_recruiter_candidate():
    """Test that a recruiter cannot PATCH another recruiter's candidate."""
    company_a = _create_company("DW Labs")
    recruiter_a = _create_user("rahul@example.com", "Rahul", company=company_a)
    recruiter_b = _create_user("priya@example.com", "Priya", company=company_a)

    candidate_b = _create_candidate("Emma", "E", "emma@example.com", recruiter_b, company_a)

    headers_a = _auth_headers_for("rahul@example.com")
    response = client.patch(
        f"/candidates/{candidate_b.id}",
        json={"first_name": "Hacked"},
        headers=headers_a,
    )

    assert response.status_code == 404


def test_recruiter_cannot_delete_other_recruiter_candidate():
    """Test that a recruiter cannot DELETE another recruiter's candidate."""
    company_a = _create_company("DW Labs")
    recruiter_a = _create_user("rahul@example.com", "Rahul", company=company_a)
    recruiter_b = _create_user("priya@example.com", "Priya", company=company_a)

    candidate_b = _create_candidate("Frank", "F", "frank@example.com", recruiter_b, company_a)

    headers_a = _auth_headers_for("rahul@example.com")
    response = client.delete(f"/candidates/{candidate_b.id}", headers=headers_a)

    assert response.status_code == 404


def test_recruiter_cannot_access_different_company_candidate():
    """Test that a recruiter cannot access a candidate from a different company."""
    company_a = _create_company("DW Labs")
    company_b = _create_company("Company B")
    recruiter_a = _create_user("rahul@example.com", "Rahul", company=company_a)
    recruiter_c = _create_user("charlie@example.com", "Charlie", company=company_b)

    candidate_b = _create_candidate("Grace", "G", "grace@example.com", recruiter_c, company_b)

    headers_a = _auth_headers_for("rahul@example.com")
    response = client.get(f"/candidates/{candidate_b.id}", headers=headers_a)

    assert response.status_code == 404


def test_recruiter_can_patch_own_candidate():
    """Test that a recruiter can PATCH their own candidate."""
    company_a = _create_company("DW Labs")
    recruiter_a = _create_user("rahul@example.com", "Rahul", company=company_a)

    candidate_a = _create_candidate("Henry", "H", "henry@example.com", recruiter_a, company_a)

    headers_a = _auth_headers_for("rahul@example.com")
    response = client.patch(
        f"/candidates/{candidate_a.id}",
        json={
            "first_name": "Harold",
            "phone": "555-9999",
        },
        headers=headers_a,
    )

    assert response.status_code == 200
    updated = response.json()
    assert updated["first_name"] == "Harold"
    assert updated["phone"] == "555-9999"


def test_recruiter_cannot_change_owner_via_patch():
    """Test that a recruiter cannot change owner_user_id via PATCH."""
    company_a = _create_company("DW Labs")
    recruiter_a = _create_user("rahul@example.com", "Rahul", company=company_a)
    recruiter_b = _create_user("priya@example.com", "Priya", company=company_a)

    candidate_a = _create_candidate("Iris", "I", "iris@example.com", recruiter_a, company_a)

    headers_a = _auth_headers_for("rahul@example.com")
    response = client.patch(
        f"/candidates/{candidate_a.id}",
        json={
            "owner_user_id": recruiter_b.id,
            "first_name": "NewIris",
        },
        headers=headers_a,
    )

    assert response.status_code == 200
    updated = response.json()
    # owner_user_id should not change
    assert updated["owner_user_id"] == recruiter_a.id
    # but first_name should update
    assert updated["first_name"] == "NewIris"


def test_recruiter_cannot_change_company_via_patch():
    """Test that a recruiter cannot change company_id via PATCH."""
    company_a = _create_company("DW Labs")
    company_b = _create_company("Company B")
    recruiter_a = _create_user("rahul@example.com", "Rahul", company=company_a)

    candidate_a = _create_candidate("Jack", "J", "jack@example.com", recruiter_a, company_a)

    headers_a = _auth_headers_for("rahul@example.com")
    response = client.patch(
        f"/candidates/{candidate_a.id}",
        json={
            "company_id": company_b.id,
            "first_name": "Jackson",
        },
        headers=headers_a,
    )

    assert response.status_code == 200
    updated = response.json()
    # company_id should not change
    assert updated["company_id"] == company_a.id
    # but first_name should update
    assert updated["first_name"] == "Jackson"


def test_recruiter_can_delete_own_candidate():
    """Test that a recruiter can DELETE their own candidate."""
    company_a = _create_company("DW Labs")
    recruiter_a = _create_user("rahul@example.com", "Rahul", company=company_a)

    candidate_a = _create_candidate("Kate", "K", "kate@example.com", recruiter_a, company_a)

    headers_a = _auth_headers_for("rahul@example.com")
    response = client.delete(f"/candidates/{candidate_a.id}", headers=headers_a)

    assert response.status_code == 204

    # Verify it's actually deleted
    response_check = client.get(f"/candidates/{candidate_a.id}", headers=headers_a)
    assert response_check.status_code == 404


# ============================================================================
# COMPANY ADMIN TESTS
# ============================================================================


def test_company_admin_can_see_all_company_candidates():
    """Test that a company admin can see all candidates in their company."""
    company_a = _create_company("DW Labs")
    recruiter_a = _create_user("rahul@example.com", "Rahul", company=company_a)
    recruiter_b = _create_user("priya@example.com", "Priya", company=company_a)
    admin_a = _create_user(
        "admin@example.com",
        "Admin A",
        role=UserRole.COMPANY_ADMIN.value,
        company=company_a,
    )

    candidate_a1 = _create_candidate("Luke", "L", "luke@example.com", recruiter_a, company_a)
    candidate_a2 = _create_candidate("Maria", "M", "maria@example.com", recruiter_b, company_a)

    headers_admin = _auth_headers_for("admin@example.com")
    response = client.get("/candidates", headers=headers_admin)

    assert response.status_code == 200
    candidates = response.json()
    assert len(candidates) == 2
    ids = {c["id"] for c in candidates}
    assert candidate_a1.id in ids
    assert candidate_a2.id in ids


def test_company_admin_can_get_specific_candidate():
    """Test that a company admin can GET a specific candidate."""
    company_a = _create_company("DW Labs")
    recruiter_a = _create_user("rahul@example.com", "Rahul", company=company_a)
    admin_a = _create_user(
        "admin@example.com",
        "Admin A",
        role=UserRole.COMPANY_ADMIN.value,
        company=company_a,
    )

    candidate_a = _create_candidate("Noah", "N", "noah@example.com", recruiter_a, company_a)

    headers_admin = _auth_headers_for("admin@example.com")
    response = client.get(f"/candidates/{candidate_a.id}", headers=headers_admin)

    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == candidate_a.id
    assert payload["email"] == "noah@example.com"


def test_company_admin_cannot_access_different_company_candidate():
    """Test that a company admin cannot access a candidate from a different company."""
    company_a = _create_company("DW Labs")
    company_b = _create_company("Company B")
    recruiter_c = _create_user("charlie@example.com", "Charlie", company=company_b)
    admin_a = _create_user(
        "admin_a@example.com",
        "Admin A",
        role=UserRole.COMPANY_ADMIN.value,
        company=company_a,
    )

    candidate_b = _create_candidate("Olivia", "O", "olivia@example.com", recruiter_c, company_b)

    headers_admin_a = _auth_headers_for("admin_a@example.com")
    response = client.get(f"/candidates/{candidate_b.id}", headers=headers_admin_a)

    assert response.status_code == 404


def test_company_admin_can_patch_any_company_candidate():
    """Test that a company admin can PATCH any candidate in their company."""
    company_a = _create_company("DW Labs")
    recruiter_a = _create_user("rahul@example.com", "Rahul", company=company_a)
    admin_a = _create_user(
        "admin@example.com",
        "Admin A",
        role=UserRole.COMPANY_ADMIN.value,
        company=company_a,
    )

    candidate_a = _create_candidate("Peter", "P", "peter@example.com", recruiter_a, company_a)

    headers_admin = _auth_headers_for("admin@example.com")
    response = client.patch(
        f"/candidates/{candidate_a.id}",
        json={"phone": "555-1234"},
        headers=headers_admin,
    )

    assert response.status_code == 200
    updated = response.json()
    assert updated["phone"] == "555-1234"
    # Verify ownership is unchanged
    assert updated["owner_user_id"] == recruiter_a.id


def test_company_admin_cannot_change_owner_via_patch():
    """Test that a company admin cannot change owner_user_id via PATCH."""
    company_a = _create_company("DW Labs")
    recruiter_a = _create_user("rahul@example.com", "Rahul", company=company_a)
    recruiter_b = _create_user("priya@example.com", "Priya", company=company_a)
    admin_a = _create_user(
        "admin@example.com",
        "Admin A",
        role=UserRole.COMPANY_ADMIN.value,
        company=company_a,
    )

    candidate_a = _create_candidate("Quinn", "Q", "quinn@example.com", recruiter_a, company_a)

    headers_admin = _auth_headers_for("admin@example.com")
    response = client.patch(
        f"/candidates/{candidate_a.id}",
        json={"owner_user_id": recruiter_b.id},
        headers=headers_admin,
    )

    assert response.status_code == 200
    updated = response.json()
    # owner_user_id should not change
    assert updated["owner_user_id"] == recruiter_a.id


def test_company_admin_can_delete_any_company_candidate():
    """Test that a company admin can DELETE any candidate in their company."""
    company_a = _create_company("DW Labs")
    recruiter_a = _create_user("rahul@example.com", "Rahul", company=company_a)
    admin_a = _create_user(
        "admin@example.com",
        "Admin A",
        role=UserRole.COMPANY_ADMIN.value,
        company=company_a,
    )

    candidate_a = _create_candidate("Rachel", "R", "rachel@example.com", recruiter_a, company_a)

    headers_admin = _auth_headers_for("admin@example.com")
    response = client.delete(f"/candidates/{candidate_a.id}", headers=headers_admin)

    assert response.status_code == 204

    # Verify it's deleted
    response_check = client.get(f"/candidates/{candidate_a.id}", headers=headers_admin)
    assert response_check.status_code == 404


# ============================================================================
# CROSS-COMPANY PROTECTION TESTS
# ============================================================================


def test_company_b_admin_cannot_see_company_a_candidates():
    """Test that admin from Company B cannot see Company A candidates."""
    company_a = _create_company("DW Labs")
    company_b = _create_company("Company B")
    recruiter_a = _create_user("rahul@example.com", "Rahul", company=company_a)
    recruiter_c = _create_user("charlie@example.com", "Charlie", company=company_b)
    admin_b = _create_user(
        "admin_b@example.com",
        "Admin B",
        role=UserRole.COMPANY_ADMIN.value,
        company=company_b,
    )

    candidate_a = _create_candidate("Steve", "S", "steve@example.com", recruiter_a, company_a)
    candidate_b = _create_candidate("Tina", "T", "tina@example.com", recruiter_c, company_b)

    headers_admin_b = _auth_headers_for("admin_b@example.com")
    response = client.get("/candidates", headers=headers_admin_b)

    assert response.status_code == 200
    candidates = response.json()
    # Should only see Company B candidates
    assert len(candidates) == 1
    assert candidates[0]["id"] == candidate_b.id
    assert candidate_a.id not in {c["id"] for c in candidates}


def test_company_a_and_b_candidates_remain_isolated():
    """Test that candidates from different companies remain completely isolated."""
    company_a = _create_company("DW Labs")
    company_b = _create_company("Company B")

    recruiter_a = _create_user("rahul@example.com", "Rahul", company=company_a)
    recruiter_c = _create_user("charlie@example.com", "Charlie", company=company_b)

    candidate_a = _create_candidate("Uma", "U", "uma@example.com", recruiter_a, company_a)
    candidate_b = _create_candidate("Victor", "V", "victor@example.com", recruiter_c, company_b)

    headers_a = _auth_headers_for("rahul@example.com")
    headers_c = _auth_headers_for("charlie@example.com")

    # Recruiter A's candidates
    response_a = client.get("/candidates", headers=headers_a)
    candidates_a = response_a.json()
    assert len(candidates_a) == 1
    assert candidates_a[0]["id"] == candidate_a.id

    # Recruiter C's candidates
    response_c = client.get("/candidates", headers=headers_c)
    candidates_c = response_c.json()
    assert len(candidates_c) == 1
    assert candidates_c[0]["id"] == candidate_b.id

    # Cross-company GET returns 404
    response_cross_a_to_b = client.get(f"/candidates/{candidate_b.id}", headers=headers_a)
    assert response_cross_a_to_b.status_code == 404

    response_cross_c_to_a = client.get(f"/candidates/{candidate_a.id}", headers=headers_c)
    assert response_cross_c_to_a.status_code == 404


# ============================================================================
# CREATION VALIDATION TESTS
# ============================================================================


def test_candidate_creation_requires_company_assignment():
    """Test that a user without company assignment cannot create candidates."""
    db = SessionLocal()
    try:
        user_no_company = User(
            full_name="Unassigned",
            email="unassigned@example.com",
            hashed_password=AuthService(db).hash_password("Password123!"),
            role=UserRole.RECRUITER.value,
            company_id=None,
            is_active=True,
        )
        db.add(user_no_company)
        db.commit()
    finally:
        db.close()

    headers = _auth_headers_for("unassigned@example.com")
    response = client.post(
        "/candidates",
        json={
            "first_name": "Walter",
            "last_name": "W",
            "email": "walter@example.com",
        },
        headers=headers,
    )

    assert response.status_code == 400
    assert "company" in response.json()["detail"].lower()


# ============================================================================
# PRIVACY ACROSS MULTIPLE RECRUITERS
# ============================================================================


def test_multiple_recruiters_see_own_candidates_only():
    """Test that multiple recruiters see only their own candidates."""
    company_a = _create_company("DW Labs")
    recruiter_a = _create_user("rahul@example.com", "Rahul", company=company_a)
    recruiter_b = _create_user("priya@example.com", "Priya", company=company_a)
    recruiter_d = _create_user("donna@example.com", "Donna", company=company_a)

    candidate_a1 = _create_candidate("Xavier", "X", "xavier@example.com", recruiter_a, company_a)
    candidate_b1 = _create_candidate("Yara", "Y", "yara@example.com", recruiter_b, company_a)
    candidate_d1 = _create_candidate("Zoe", "Z", "zoe@example.com", recruiter_d, company_a)

    headers_a = _auth_headers_for("rahul@example.com")
    headers_b = _auth_headers_for("priya@example.com")
    headers_d = _auth_headers_for("donna@example.com")

    response_a = client.get("/candidates", headers=headers_a)
    response_b = client.get("/candidates", headers=headers_b)
    response_d = client.get("/candidates", headers=headers_d)

    candidates_a = response_a.json()
    candidates_b = response_b.json()
    candidates_d = response_d.json()

    assert len(candidates_a) == 1
    assert len(candidates_b) == 1
    assert len(candidates_d) == 1

    assert candidates_a[0]["id"] == candidate_a1.id
    assert candidates_b[0]["id"] == candidate_b1.id
    assert candidates_d[0]["id"] == candidate_d1.id
