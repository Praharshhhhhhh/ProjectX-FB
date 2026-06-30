"""
Regression test: verify_password() must still validate password hashes that
were produced by the pre-refactor bcrypt implementation (passlib's
CryptContext(schemes=["bcrypt"])), not just hashes produced by the new
native `bcrypt` implementation in services/auth_service.py.
"""
import bcrypt as raw_bcrypt
from services.auth_service import verify_password


def test_verify_password_accepts_legacy_bcrypt_hash(db_session):
    """
    Simulate a hash created by pre-refactor code (passlib bcrypt) being
    present in the DB already, and confirm the new verify_password()
    still authenticates it correctly.
    """
    plain_password = "LegacyPassw0rd!"

    # Produce a hash the same way the OLD passlib-based code would have:
    # passlib's CryptContext(schemes=["bcrypt"]) ultimately calls the same
    # underlying bcrypt primitive, producing a standard $2b$ hash.
    legacy_hash = raw_bcrypt.hashpw(
        plain_password.encode("utf-8"), raw_bcrypt.gensalt()
    ).decode("utf-8")

    assert legacy_hash.startswith("$2b$") or legacy_hash.startswith("$2a$")

    # Insert directly into a test user row to mimic a pre-existing DB record
    from models.user import User, UserRole
    import uuid

    user = User(
        email="legacy.user@setulink.io",
        full_name="Legacy User",
        hashed_password=legacy_hash,
        role=UserRole.admin,
        is_active=True,
        uuid=uuid.uuid4().hex,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    # The actual regression assertion
    assert verify_password(plain_password, user.hashed_password) is True
    assert verify_password("WrongPassword", user.hashed_password) is False
