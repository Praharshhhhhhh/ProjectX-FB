import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from config import get_settings
from database import Base, engine
from models import User, UserRole
from services.auth_service import hash_password
from apscheduler.schedulers.background import BackgroundScheduler
from services.gateway_provisioning_service import resync_gateway_state, reconcile_gateway_peers, prune_stale_desktop_peers
import models  # ensure all models are imported before create_all

from routers import auth, admin, users
from routers import routers as routers_router

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    _seed_system_owner()
    scheduler = BackgroundScheduler()
    scheduler.add_job(resync_gateway_state, 'interval', seconds=30)
    scheduler.add_job(reconcile_gateway_peers, 'interval', seconds=60)
    scheduler.add_job(prune_stale_desktop_peers, 'interval', seconds=60)
    scheduler.start()
    yield
    scheduler.shutdown()


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="SetuLink REST API — Router Claim & Activation system.",
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
for r in [auth.router, admin.router, users.router, routers_router.router, routers_router.desktop_router]:
    app.include_router(r)


# ─── Startup ───────────────────────────────────────────────────────────────────

def _seed_system_owner():
    from database import SessionLocal
    db = SessionLocal()
    try:
        owner = db.query(User).filter(User.email == settings.OWNER_EMAIL).first()
        if not owner:
            import uuid
            owner = User(
                email=settings.OWNER_EMAIL,
                full_name="System Owner",
                hashed_password=hash_password(settings.OWNER_PASSWORD),
                role=UserRole.system_owner,
                is_active=True,
                uuid=uuid.uuid4().hex,
            )
            db.add(owner)
            db.commit()
            print("System Owner created")
            
        # Seed TableAllocator if missing
        from models.table_allocator import TableAllocator
        alloc = db.query(TableAllocator).first()
        if not alloc:
            db.add(TableAllocator(next_wg_ip_octet=2, next_table_id=100))
            db.commit()
            print("TableAllocator seeded")
            
    finally:
        db.close()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8002, reload=True)
