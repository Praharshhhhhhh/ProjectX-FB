import os
import sys
import uuid
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from database import SessionLocal
from models import Tenant, TenantStatus, User, UserRole
from services.auth_service import hash_password

db = SessionLocal()
try:
    tenant = db.query(Tenant).filter_by(company_name="Test Corp").first()
    if not tenant:
        tenant = Tenant(
            company_name="Test Corp",
            status=TenantStatus.active
        )
        db.add(tenant)
        db.commit()
        db.refresh(tenant)
        print("Created tenant!")
        
    user = db.query(User).filter_by(email="test@test.com").first()
    if not user:
        user = User(
            email="test@test.com",
            full_name="Test User",
            hashed_password=hash_password("password"),
            tenant_id=tenant.id,
            role=UserRole.admin,
            is_active=True,
            uuid=uuid.uuid4().hex
        )
        db.add(user)
        db.commit()
        print("Created test user: test@test.com / password")
finally:
    db.close()
