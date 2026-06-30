from datetime import datetime
from fastapi import HTTPException
from sqlalchemy.orm import Session
from models.router import Router, RouterStatus
from models.activation_key import ActivationKey
from models import User


def claim_router(db: Session, current_user: User, serial_number: str, activation_key: str) -> Router:
    """Claim a router with exact validation order per spec §11."""
    if db.bind.dialect.name == "sqlite":
        from sqlalchemy import text
        db.execute(text("BEGIN IMMEDIATE"))

    # 1. Find router by serial number (row-locked for concurrency safety)
    router = db.query(Router).filter(
        Router.serial_number == serial_number
    ).with_for_update().first()
    if not router:
        raise HTTPException(status_code=404, detail="Router not found.")

    # 2. Check if already claimed
    if router.status not in (RouterStatus.prepared, RouterStatus.pending_validation):
        raise HTTPException(status_code=409, detail="Router already claimed.")

    # 3. Find activation key
    key = db.query(ActivationKey).filter(
        ActivationKey.key_code == activation_key
    ).first()
    if not key:
        raise HTTPException(status_code=400, detail="Invalid Activation Key.")

    # 4. Key must belong to this router
    if key.router_id != router.id:
        raise HTTPException(status_code=400, detail="Invalid Activation Key.")

    # 5. Key must not be used
    if key.is_used:
        raise HTTPException(status_code=400, detail="Activation Key already used.")

    # 6. Commit all changes atomically
    now = datetime.utcnow()
    router.tenant_id = current_user.tenant_id
    router.claimed_by_user_id = current_user.id
    router.status = RouterStatus.claimed
    router.claimed_at = now

    key.is_used = True
    key.used_by_user_id = current_user.id
    key.used_at = now

    db.commit()
    db.refresh(router)
    return router
