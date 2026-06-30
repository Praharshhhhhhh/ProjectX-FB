import pytest
import threading
import time
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Tenant, User, UserRole, Router, RouterStatus, ActivationKey, PendingValidation, PendingValidationStatus
from services.auth_service import create_access_token, hash_password
from cryptography.fernet import Fernet
from database import Base
from config import get_settings

settings = get_settings()

def _headers(user: User) -> dict:
    token = create_access_token({"user_id": user.id, "uuid": user.uuid, "role": user.role, "tenant_id": user.tenant_id})
    return {"Authorization": f"Bearer {token}", "X-User-Identifier": user.uuid}

def _setup_tenant_and_users(db):
    tenant = Tenant(company_name="Test Tenant")
    db.add(tenant)
    db.flush()

    master = User(
        email="master@test.com",
        full_name="Master User",
        hashed_password=hash_password("Pass123!"),
        role=UserRole.master,
        tenant_id=tenant.id,
        uuid="uuid-master"
    )
    second_master = User(
        email="second@test.com",
        full_name="Second Master",
        hashed_password=hash_password("Pass123!"),
        role=UserRole.second_master,
        tenant_id=tenant.id,
        uuid="uuid-second"
    )
    admin = User(
        email="admin@test.com",
        full_name="Admin User",
        hashed_password=hash_password("Pass123!"),
        role=UserRole.admin,
        tenant_id=tenant.id,
        uuid="uuid-admin"
    )
    trusted = User(
        email="trusted@test.com",
        full_name="Trusted User",
        hashed_password=hash_password("Pass123!"),
        role=UserRole.trusted,
        tenant_id=tenant.id,
        uuid="uuid-trusted"
    )
    db.add_all([master, second_master, admin, trusted])
    db.commit()
    return tenant, master, second_master, admin, trusted

def _setup_router(db, router_id="rt-1", serial="sn-1", mac="mac-1"):
    router = Router(
        router_id=router_id,
        serial_number=serial,
        mac_address=mac,
        status=RouterStatus.prepared
    )
    db.add(router)
    db.flush()
    key = ActivationKey(router_id=router.id, key_code=f"key-{router_id}")
    db.add(key)
    db.commit()
    return router, key

def test_master_can_claim_router(client, db_session):
    _, master, _, _, _ = _setup_tenant_and_users(db_session)
    router, key = _setup_router(db_session)

    res = client.post(
        "/api/routers/claim",
        json={"serial_number": router.serial_number, "activation_key": key.key_code},
        headers=_headers(master)
    )
    assert res.status_code == 200
    assert res.json()["status"] == "claimed"
    assert res.json()["router"]["status"] == "claimed"

def test_second_master_can_claim_router(client, db_session):
    _, _, second_master, _, _ = _setup_tenant_and_users(db_session)
    router, key = _setup_router(db_session)

    res = client.post(
        "/api/routers/claim",
        json={"serial_number": router.serial_number, "activation_key": key.key_code},
        headers=_headers(second_master)
    )
    assert res.status_code == 200

def test_admin_cannot_claim_router(client, db_session):
    _, _, _, admin, _ = _setup_tenant_and_users(db_session)
    router, key = _setup_router(db_session)

    res = client.post(
        "/api/routers/claim",
        json={"serial_number": router.serial_number, "activation_key": key.key_code},
        headers=_headers(admin)
    )
    assert res.status_code == 403

def test_trusted_cannot_claim_router(client, db_session):
    _, _, _, _, trusted = _setup_tenant_and_users(db_session)
    router, key = _setup_router(db_session)

    res = client.post(
        "/api/routers/claim",
        json={"serial_number": router.serial_number, "activation_key": key.key_code},
        headers=_headers(trusted)
    )
    assert res.status_code == 403

def test_online_claim_sets_status_claimed_immediately(client, db_session):
    _, master, _, _, _ = _setup_tenant_and_users(db_session)
    router, key = _setup_router(db_session)

    client.post(
        "/api/routers/claim",
        json={"serial_number": router.serial_number, "activation_key": key.key_code},
        headers=_headers(master)
    )

    db_session.expire_all()
    r = db_session.query(Router).filter(Router.id == router.id).first()
    assert r.status == RouterStatus.claimed

def test_duplicate_key_submission_returns_already_used(client, db_session):
    tenant, master, _, _, _ = _setup_tenant_and_users(db_session)
    router, key = _setup_router(db_session)

    # Use key first
    key.is_used = True
    key.used_by_user_id = master.id
    db_session.commit()

    res = client.post(
        "/api/routers/claim",
        json={"serial_number": router.serial_number, "activation_key": key.key_code},
        headers=_headers(master)
    )
    assert res.status_code == 400
    assert "already used" in res.json()["detail"].lower()

def test_wrong_activation_key_returns_invalid(client, db_session):
    _, master, _, _, _ = _setup_tenant_and_users(db_session)
    router, _ = _setup_router(db_session)

    res = client.post(
        "/api/routers/claim",
        json={"serial_number": router.serial_number, "activation_key": "wrongkey"},
        headers=_headers(master)
    )
    assert res.status_code == 400
    assert "invalid" in res.json()["detail"].lower()

def test_unknown_serial_returns_router_not_found(client, db_session):
    _, master, _, _, _ = _setup_tenant_and_users(db_session)
    _setup_router(db_session)

    res = client.post(
        "/api/routers/claim",
        json={"serial_number": "unknown-sn", "activation_key": "anykey"},
        headers=_headers(master)
    )
    assert res.status_code == 404
    assert "not found" in res.json()["detail"].lower()

def test_already_claimed_router_returns_already_claimed(client, db_session):
    _, master, _, _, _ = _setup_tenant_and_users(db_session)
    router, key = _setup_router(db_session)

    router.status = RouterStatus.claimed
    db_session.commit()

    res = client.post(
        "/api/routers/claim",
        json={"serial_number": router.serial_number, "activation_key": key.key_code},
        headers=_headers(master)
    )
    assert res.status_code == 409
    assert "already claimed" in res.json()["detail"].lower()

def test_pending_validation_only_visible_to_claiming_user(client, db_session):
    tenant, master, second_master, _, _ = _setup_tenant_and_users(db_session)
    router, _ = _setup_router(db_session)

    # Set router to pending validation
    router.status = RouterStatus.pending_validation
    router.claimed_by_user_id = master.id
    db_session.commit()

    # Create PendingValidation row
    pv = PendingValidation(
        router_id=router.id,
        tenant_id=tenant.id,
        claimed_by_user_id=master.id,
        serial_number_submitted=router.serial_number,
        key_code_submitted="somekey",
        status=PendingValidationStatus.pending
    )
    db_session.add(pv)
    db_session.commit()

    # Request as master
    res = client.get("/api/routers", headers=_headers(master))
    assert len(res.json()) == 1

    # Request as second_master
    res2 = client.get("/api/routers", headers=_headers(second_master))
    assert len(res2.json()) == 0

def test_share_disabled_while_pending_validation(client, db_session):
    _, master, _, _, _ = _setup_tenant_and_users(db_session)
    router, _ = _setup_router(db_session)

    router.status = RouterStatus.pending_validation
    db_session.commit()

    res = client.post(f"/api/routers/{router.id}/share", headers=_headers(master))
    assert res.status_code == 403
    assert "sharing is unavailable" in res.json()["detail"]

def test_share_enabled_after_claimed(client, db_session):
    _, master, _, _, _ = _setup_tenant_and_users(db_session)
    router, _ = _setup_router(db_session)

    router.status = RouterStatus.claimed
    db_session.commit()

    res = client.post(f"/api/routers/{router.id}/share", headers=_headers(master))
    assert res.status_code == 200

def test_sync_completes_pending_validation_and_marks_claimed(client, db_session):
    tenant, master, _, _, _ = _setup_tenant_and_users(db_session)
    router, key = _setup_router(db_session)

    # Encrypt the key code
    encrypted_key = key.key_code
    if settings.FIELD_ENCRYPTION_KEY:
        f = Fernet(settings.FIELD_ENCRYPTION_KEY.encode())
        encrypted_key = f.encrypt(key.key_code.encode()).decode()

    router.status = RouterStatus.pending_validation
    router.claimed_by_user_id = master.id
    db_session.commit()

    pv = PendingValidation(
        router_id=router.id,
        tenant_id=tenant.id,
        claimed_by_user_id=master.id,
        serial_number_submitted=router.serial_number,
        key_code_submitted=encrypted_key,
        status=PendingValidationStatus.pending
    )
    db_session.add(pv)
    db_session.commit()

    res = client.post(f"/api/routers/{router.id}/sync", headers=_headers(master))
    assert res.status_code == 200

    db_session.expire_all()
    assert pv.status == PendingValidationStatus.completed
    assert router.status == RouterStatus.claimed

def test_concurrent_claim_attempts_only_one_succeeds(db_session):
    tenant, master, _, _, _ = _setup_tenant_and_users(db_session)
    router, key = _setup_router(db_session)
    
    # We must use threading to test concurrent claims.
    # Note: SQLite on in-memory db uses a shared-cache or local lock.
    # Since we used with_for_update(), we need to test with two threads calling claim_router.
    # We will use two separate DB sessions pointing to the same memory DB (need to use a shared connection or file database for that).
    # Since SQLAlchemy with :memory: doesn't easily share tables between separate connections unless we manage the connection,
    # let's create a temporary file-based SQLite database for this specific test.
    import tempfile
    import os
    fd, temp_db_path = tempfile.mkstemp()
    os.close(fd)
    
    temp_url = f"sqlite:///{temp_db_path}"
    engine = create_engine(temp_url, connect_args={"timeout": 15})
    Session = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)
    
    try:
        # Set up data in temp db
        db1 = Session()
        t = Tenant(company_name="Temp Tenant")
        db1.add(t)
        db1.flush()
        m = User(email="m@t.com", full_name="M", hashed_password="pw", role=UserRole.master, tenant_id=t.id)
        db1.add(m)
        r = Router(router_id="rt", serial_number="sn", mac_address="mac", status=RouterStatus.prepared)
        db1.add(r)
        db1.flush()
        k = ActivationKey(router_id=r.id, key_code="kc")
        db1.add(k)
        db1.commit()
        
        user_id = m.id
        router_serial = r.serial_number
        key_code = k.key_code
        db1.close()
        
        results = []
        
        def run_claim():
            db = Session()
            try:
                # Retrieve fresh user object
                user_obj = db.query(User).filter(User.id == user_id).first()
                from services.router_claim_service import claim_router as service_claim
                service_claim(db, user_obj, router_serial, key_code)
                results.append("success")
            except Exception as e:
                results.append(str(e))
            finally:
                db.close()
                
        t1 = threading.Thread(target=run_claim)
        t2 = threading.Thread(target=run_claim)
        
        t1.start()
        t2.start()
        
        t1.join()
        t2.join()
        
        # One should succeed, one should fail (either 409 already claimed, or database locks/rollbacks)
        successes = [r for r in results if r == "success"]
        failures = [r for r in results if r != "success"]
        
        assert len(successes) == 1
        assert len(failures) == 1
    finally:
        Base.metadata.drop_all(bind=engine)
        engine.dispose()
        try:
            os.remove(temp_db_path)
        except Exception:
            pass
