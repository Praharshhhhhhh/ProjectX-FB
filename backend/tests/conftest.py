import os
# Set env var before importing anything from database/main to prevent Postgres connection
os.environ["DATABASE_URL"] = "sqlite:///./test_database.db"

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from database import Base, get_db
import models
from main import app
from fastapi.testclient import TestClient
from unittest.mock import patch
from cryptography.fernet import Fernet

SQLALCHEMY_DATABASE_URL = "sqlite:///./test_database.db"

@pytest.fixture(scope="session", autouse=True)
def setup_test_settings():
    from config import get_settings
    settings = get_settings()
    settings.DATABASE_URL = SQLALCHEMY_DATABASE_URL
    # Generate a valid Fernet key for tests
    settings.FIELD_ENCRYPTION_KEY = Fernet.generate_key().decode()
    settings.OTP_RESEND_COOLDOWN_SECONDS = 2
    settings.SECRET_KEY = "test-secret"
    yield
    # Cleanup after session
    try:
        import os
        if os.path.exists("test_database.db"):
            # Close engine connection pool first
            from database import engine
            engine.dispose()
            os.remove("test_database.db")
    except Exception:
        pass

@pytest.fixture(scope="function")
def db_session():
    from database import engine
    
    # Clean up tables if they exist
    Base.metadata.drop_all(bind=engine, checkfirst=True)
    
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine, checkfirst=True)
    
    # Seed owner user
    from models.user import User, UserRole
    from services.auth_service import hash_password
    import uuid
    
    db = TestingSessionLocal()
    tenant = models.tenant.Tenant(company_name="System Tenant")
    db.add(tenant)
    db.commit()
    
    owner = User(
        email="owner@setulink.io",
        full_name="System Owner",
        hashed_password=hash_password("Admin@123"),
        role=UserRole.system_owner,
        is_active=True,
        uuid=uuid.uuid4().hex,
        tenant_id=tenant.id
    )
    db.add(owner)
    
    alloc = models.table_allocator.TableAllocator(next_wg_ip_octet=2)
    db.add(alloc)
    
    db.commit()
    db.close()

    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine, checkfirst=True)

@pytest.fixture(scope="function")
def client(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()

@pytest.fixture(scope="function")
def mock_email():
    with patch("services.email_service.send_email") as mock:
        yield mock

@pytest.fixture(scope="function", autouse=True)
def mock_requests():
    with patch("requests.post") as mock_post, patch("requests.delete") as mock_delete:
        mock_post.return_value.status_code = 200
        mock_delete.return_value.status_code = 200
        yield mock_post, mock_delete
