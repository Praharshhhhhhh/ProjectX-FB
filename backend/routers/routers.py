from datetime import datetime
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from models import User, UserRole, Router, RouterStatus, PendingValidation, PendingValidationStatus
from models.activation_key import ActivationKey
from routers.deps import get_current_user, require_roles
from services.router_claim_service import claim_router
from pydantic import BaseModel
from config import get_settings

router = APIRouter(prefix="/api/routers", tags=["routers"])

settings = get_settings()


# ── Schemas (local to this router) ─────────────────────────────────────────────

class ClaimRequest(BaseModel):
    serial_number: str
    activation_key: str


class RenameRequest(BaseModel):
    name: str


def _router_dict(r: Router) -> dict:
    return {
        "id": r.id,
        "router_id": r.router_id,
        "serial_number": r.serial_number,
        "mac_address": r.mac_address,
        "name": r.name,
        "status": r.status,
        "tenant_id": r.tenant_id,
        "claimed_by_user_id": r.claimed_by_user_id,
        "prepared_at": r.prepared_at.isoformat() if r.prepared_at else None,
        "claimed_at": r.claimed_at.isoformat() if r.claimed_at else None,
    }


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.post("/claim")
def claim(
    req: ClaimRequest,
    current_user: Annotated[User, Depends(require_roles(UserRole.master, UserRole.second_master))],
    db: Annotated[Session, Depends(get_db)],
):
    result = claim_router(db, current_user, req.serial_number, req.activation_key)
    return {"status": "claimed", "router": _router_dict(result)}


@router.get("/")
def list_routers(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    # All claimed routers for user's tenant
    claimed = db.query(Router).filter(
        Router.tenant_id == current_user.tenant_id,
        Router.status == RouterStatus.claimed,
    ).all()

    # Pending validations only visible to the claiming user
    pending_rows = db.query(PendingValidation).filter(
        PendingValidation.claimed_by_user_id == current_user.id,
        PendingValidation.status.in_([
            PendingValidationStatus.pending,
            PendingValidationStatus.syncing,
            PendingValidationStatus.failed,
        ]),
    ).all()

    pending_router_ids = [pv.router_id for pv in pending_rows]
    pending_routers = []
    if pending_router_ids:
        pending_routers = db.query(Router).filter(Router.id.in_(pending_router_ids)).all()

    result = [_router_dict(r) for r in claimed]
    for r in pending_routers:
        if r.id not in {cr.id for cr in claimed}:
            result.append(_router_dict(r))
    return result


@router.patch("/{router_id}/rename")
def rename_router(
    router_id: int,
    req: RenameRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    r = db.query(Router).filter(Router.id == router_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="Router not found.")

    # Allowed if pending_validation + user is claimer, or claimed + same tenant
    if r.status == RouterStatus.pending_validation:
        if r.claimed_by_user_id != current_user.id:
            raise HTTPException(status_code=403, detail="Not authorized.")
    elif r.status == RouterStatus.claimed:
        if r.tenant_id != current_user.tenant_id:
            raise HTTPException(status_code=403, detail="Not authorized.")
    else:
        raise HTTPException(status_code=403, detail="Not authorized.")

    r.name = req.name
    db.commit()
    return {"message": "Router renamed.", "router": _router_dict(r)}


@router.post("/{router_id}/share")
def share_router(
    router_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    r = db.query(Router).filter(Router.id == router_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="Router not found.")

    if r.status != RouterStatus.claimed:
        raise HTTPException(
            status_code=403,
            detail="Router is not yet validated; sharing is unavailable until activation completes.",
        )

    # Stub: sharing is gated but not fully implemented per spec
    return {"message": "Share endpoint ready. No-op success."}


@router.post("/{router_id}/sync")
def sync_router(
    router_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    pv = db.query(PendingValidation).filter(
        PendingValidation.router_id == router_id,
        PendingValidation.claimed_by_user_id == current_user.id,
        PendingValidation.status.in_([
            PendingValidationStatus.pending,
            PendingValidationStatus.failed,
        ]),
    ).first()
    if not pv:
        raise HTTPException(status_code=404, detail="No pending validation found.")

    # Decrypt key_code_submitted
    key_code = pv.key_code_submitted
    if settings.FIELD_ENCRYPTION_KEY:
        try:
            from cryptography.fernet import Fernet
            f = Fernet(settings.FIELD_ENCRYPTION_KEY.encode())
            key_code = f.decrypt(pv.key_code_submitted.encode()).decode()
        except Exception:
            pass  # If decryption fails, try raw value

    pv.status = PendingValidationStatus.syncing
    pv.last_sync_attempt_at = datetime.utcnow()
    db.commit()

    try:
        result = claim_router(db, current_user, pv.serial_number_submitted, key_code)
        pv.status = PendingValidationStatus.completed
        db.commit()
        return {"status": "claimed", "router": _router_dict(result)}
    except HTTPException as e:
        pv.status = PendingValidationStatus.failed
        pv.fail_reason = e.detail
        pv.last_sync_attempt_at = datetime.utcnow()
        db.commit()
        raise
