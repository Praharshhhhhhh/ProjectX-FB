import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

# pyrefly: ignore [missing-import]
from config import get_settings
# pyrefly: ignore [missing-import]
from database import Base, engine
# pyrefly: ignore [missing-import]
from models import User, UserRole
# pyrefly: ignore [missing-import]
from services.auth_service import hash_password
# pyrefly: ignore [missing-import]
import models  # ensure all models are imported before create_all

# pyrefly: ignore [missing-import]
from routers import auth, admin, users, devices, lan_devices, audit, ws, device_shares
# pyrefly: ignore [missing-import]
from services.device_monitor import run_monitor_loop

settings = get_settings()

@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    _seed_system_owner()
    
    # Deprecated: The backend no longer runs its own VPN Hub
    # from services.wireguard_controller import start_hub
    # start_hub()
    
    await _rebuild_wireguard_peers()
    
    task = asyncio.create_task(run_monitor_loop(30))
    yield
    task.cancel()

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="ProjectX REST API — all UI is served by the PyQt6 desktop client.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── API Routers ───────────────────────────────────────────────────────────────
for r in [auth.router, admin.router, users.router, devices.router, lan_devices.router, audit.router, ws.router, device_shares.router]:
    app.include_router(r)


# ─── Startup ───────────────────────────────────────────────────────────────────
# Managed by lifespan context manager


def _seed_system_owner():
    # pyrefly: ignore [missing-import]
    from database import SessionLocal
    db = SessionLocal()
    try:
        owner = db.query(User).filter(User.role == UserRole.system_owner).first()
        if not owner:
            import uuid
            owner = User(
                email=settings.OWNER_EMAIL,
                full_name="System Owner",
                hashed_password=hash_password(settings.OWNER_PASSWORD),
                role=UserRole.system_owner,
                is_active=True,
                uuid=uuid.uuid4().hex
            )
            db.add(owner)
            db.commit()
            print("✅ System Owner created: owner@projectx.io / Admin@123")
    finally:
        db.close()

async def _rebuild_wireguard_peers():
    # Deprecated: The backend no longer forcefully manages WireGuard interfaces locally.
    # We broadcast a mesh_updated event to all tenants so connected Hubs reconcile themselves.
    from database import SessionLocal
    from models import Tenant
    from services.websocket_manager import manager
    
    db = SessionLocal()
    try:
        tenants = db.query(Tenant).all()
        for t in tenants:
            await manager.broadcast_to_tenant(t.id, {"event": "mesh_updated"})
        print(f"✅ Sent mesh_updated broadcast to {len(tenants)} tenants for Hub reconciliation")
    except Exception as e:
        print(f"Failed to broadcast mesh_updated: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8001, reload=True)
