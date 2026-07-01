from datetime import datetime
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from database import get_db
from models import User, UserRole, Router, RouterStatus, PendingValidation, PendingValidationStatus, RouterShare
from models.activation_key import ActivationKey
from routers.deps import get_current_user, require_roles
from services.router_claim_service import claim_router
from pydantic import BaseModel
from config import get_settings

from models.table_allocator import TableAllocator
from models.desktop_peer import DesktopPeer
from models.subnet_registry import SubnetRegistry
from sqlalchemy import text

router = APIRouter(prefix="/api/routers", tags=["routers"])
desktop_router = APIRouter(prefix="/api/desktop", tags=["desktop"])

settings = get_settings()


# ── Schemas (local to this router) ─────────────────────────────────────────────

class ClaimRequest(BaseModel):
    serial_number: str
    activation_key: str


class RenameRequest(BaseModel):
    name: str


class ShareRequest(BaseModel):
    user_id: int


# ─── Desktop Endpoints ─────────────────────────────────────────────────────────

class DesktopRegisterRequest(BaseModel):
    public_key: str
    device_name: str

class DesktopHeartbeatRequest(BaseModel):
    public_key: str

@desktop_router.post("/register")
def register_desktop(
    req: DesktopRegisterRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    # 1. Idempotency Check: if peer already exists by device_name, reuse it and update pubkey
    peer = db.query(DesktopPeer).filter(
        DesktopPeer.user_id == current_user.id,
        DesktopPeer.device_name == req.device_name
    ).first()
    if peer:
        peer.public_key = req.public_key
        peer.last_seen = datetime.utcnow()
        peer.active = True
        peer.tunnel_state = "connected"
        db.commit()
    else:
        # 2. Lock allocator row for SQLite/Postgres compatibility
        if db.bind.dialect.name == "sqlite":
            db.execute(text("BEGIN IMMEDIATE"))
            
        allocator = db.query(TableAllocator).with_for_update().first()
        if not allocator:
            raise HTTPException(status_code=500, detail="TableAllocator not seeded")
            
        octet = allocator.next_wg_ip_octet
        allocator.next_wg_ip_octet += 1
        db.commit()
        
        wg_ip = f"10.200.0.{octet}"
        
        # 3. Create DesktopPeer
        peer = DesktopPeer(
            user_id=current_user.id,
            tenant_id=current_user.tenant_id,
            public_key=req.public_key,
            wg_ip=wg_ip,
            device_name=req.device_name,
            active=True,
            tunnel_state="connected"
        )
        db.add(peer)
        db.commit()
        db.refresh(peer)
        
        # 3.5 Notify Gateway immediately (best-effort)
        try:
            import requests
            requests.post(
                "http://127.0.0.1:8080/v1/peers",
                json={"public_key": req.public_key, "allowed_ips": f"{wg_ip}/32"},
                timeout=2
            )
        except Exception:
            pass

    # 4. Fetch allowed IPs (all claimed subnets in the tenant)
    subnets = db.query(SubnetRegistry).filter(SubnetRegistry.tenant_id == current_user.tenant_id).all()
    allowed_ips = [s.lan_subnet for s in subnets]
    
    return {
        "wg_ip": peer.wg_ip,
        "endpoint": f"{settings.APP_NAME.lower()}.example.com:51820", # placeholder endpoint
        "allowed_ips": allowed_ips
    }

@desktop_router.post("/heartbeat")
def heartbeat_desktop(
    req: DesktopHeartbeatRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    peer = db.query(DesktopPeer).filter(
        DesktopPeer.public_key == req.public_key,
        DesktopPeer.user_id == current_user.id
    ).first()
    if not peer:
        raise HTTPException(status_code=404, detail="Desktop peer not found")
        
    peer.last_seen = datetime.utcnow()
    peer.active = True
    db.commit()
    return {"status": "ok"}

@desktop_router.post("/disconnect")
def disconnect_desktop(
    req: DesktopHeartbeatRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    peer = db.query(DesktopPeer).filter(
        DesktopPeer.public_key == req.public_key,
        DesktopPeer.user_id == current_user.id
    ).first()
    if not peer:
        raise HTTPException(status_code=404, detail="Desktop peer not found")
        
    peer.last_seen = datetime.utcnow()
    peer.active = False
    peer.tunnel_state = "disconnected"
    db.commit()
    
    # Notify Gateway immediately (best-effort) to prune it
    try:
        import requests
        requests.delete(
            f"http://127.0.0.1:8080/v1/peers/{req.public_key}",
            timeout=2
        )
    except Exception:
        pass

    return {"status": "ok"}

@desktop_router.get("/config")
def get_desktop_config(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    peer = db.query(DesktopPeer).filter(
        DesktopPeer.user_id == current_user.id
    ).first()
    if not peer:
        raise HTTPException(status_code=404, detail="Desktop peer not registered")
        
    subnets = db.query(SubnetRegistry).filter(SubnetRegistry.tenant_id == current_user.tenant_id).all()
    allowed_ips = [s.lan_subnet for s in subnets]
    
    return {
        "wg_ip": peer.wg_ip,
        "endpoint": f"192.168.29.222:51820", # Gateway PC IP
        "gateway_pubkey": settings.GATEWAY_PUBKEY,
        "allowed_ips": allowed_ips,
        "public_key": peer.public_key,
        "active": peer.active,
        "last_seen": peer.last_seen.isoformat() if peer.last_seen else None
    }


def _router_dict(r: Router) -> dict:
    return {
        "id": r.id,
        "router_id": r.router_id,
        "serial_number": r.serial_number,
        "mac_address": r.mac_address,
        "zerotier_node_id": r.zerotier_node_id,
        "wg_pubkey": None,
        "wg_ip": None,
        "last_seen": r.last_seen.isoformat() if r.last_seen else None,
        "name": r.name,
        "status": r.status,
        "tenant_id": r.tenant_id,
        "claimed_by_user_id": r.claimed_by_user_id,
        "prepared_at": r.prepared_at.isoformat() if r.prepared_at else None,
        "claimed_at": r.claimed_at.isoformat() if r.claimed_at else None,
    }


# ── Edge Router Agent Endpoints ───────────────────────────────────────────────

class RouterProvisionRequest(BaseModel):
    serial_number: str
    activation_key: str
    zerotier_node_id: str

class RouterHeartbeatRequest(BaseModel):
    serial_number: str

@router.post("/provision")
def provision_router(req: RouterProvisionRequest, db: Annotated[Session, Depends(get_db)]):
    db_router = db.query(Router).filter(Router.serial_number == req.serial_number).first()
    if not db_router:
        raise HTTPException(status_code=404, detail="Router not found")
        
    ak = db.query(ActivationKey).filter(ActivationKey.router_id == db_router.id).first()
    if not ak:
        raise HTTPException(status_code=403, detail="Router not prepared properly")
        
    if db_router.status != RouterStatus.claimed or not ak.is_used:
        raise HTTPException(status_code=403, detail="Router must be claimed in the dashboard before provisioning")
        
    key_val = ak.key_code
    if settings.FIELD_ENCRYPTION_KEY:
        try:
            from cryptography.fernet import Fernet
            f = Fernet(settings.FIELD_ENCRYPTION_KEY.encode())
            key_val = f.decrypt(ak.key_code.encode()).decode()
        except Exception:
            pass
            
    if req.activation_key != key_val:
        raise HTTPException(status_code=403, detail="Invalid activation key")
        
    db_router.zerotier_node_id = req.zerotier_node_id
    db_router.last_seen = datetime.utcnow()
    db.commit()
    
    # We must wait for the background Gateway Provisioning Service to provision the SubnetRegistry
    # Once it has successfully joined ZT and stored router_zt_ip, we can return ok.
    registry = db.query(SubnetRegistry).filter(SubnetRegistry.router_id == db_router.id).first()
    
    if not registry or registry.claimed_state != "active":
        # The agent should retry if it sees status pending
        return {"status": "pending", "message": "Provisioning in progress, please retry."}
        
    return {
        "status": "ok",
        "zt_network_id": settings.GLOBAL_ZT_NETWORK_ID
    }

@router.post("/heartbeat")
def heartbeat_router(req: RouterHeartbeatRequest, db: Annotated[Session, Depends(get_db)]):
    db_router = db.query(Router).filter(Router.serial_number == req.serial_number).first()
    if not db_router:
        raise HTTPException(status_code=404, detail="Router not found")
    db_router.last_seen = datetime.utcnow()
    db.commit()
    return {"status": "ok"}


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.post("/claim")
def claim(
    req: ClaimRequest,
    current_user: Annotated[User, Depends(require_roles(UserRole.master, UserRole.second_master))],
    db: Annotated[Session, Depends(get_db)],
    bg_tasks: BackgroundTasks,
):
    result = claim_router(db, current_user, req.serial_number, req.activation_key, bg_tasks)
    return {"status": "claimed", "router": _router_dict(result)}


@router.get("/")
def list_routers(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    if current_user.role in (UserRole.system_owner, UserRole.master, UserRole.second_master):
        # All claimed routers for user's tenant
        claimed = db.query(Router).filter(
            Router.tenant_id == current_user.tenant_id,
            Router.status == RouterStatus.claimed,
        ).all()
    else:
        # Admins and trusted users only see explicitly shared routers
        claimed = db.query(Router).join(RouterShare).filter(
            Router.tenant_id == current_user.tenant_id,
            Router.status == RouterStatus.claimed,
            RouterShare.user_id == current_user.id
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
    req: ShareRequest,
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

    if current_user.role not in (UserRole.master, UserRole.second_master):
        raise HTTPException(status_code=403, detail="Only Master or Second Master can share routers.")

    target_user = db.query(User).filter(User.id == req.user_id, User.tenant_id == current_user.tenant_id).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="Target user not found in this tenant.")

    existing_share = db.query(RouterShare).filter(RouterShare.router_id == router_id, RouterShare.user_id == target_user.id).first()
    if existing_share:
        return {"message": "Router is already shared with this user."}

    share = RouterShare(
        router_id=router_id,
        user_id=target_user.id,
        granted_by_user_id=current_user.id
    )
    db.add(share)
    db.commit()

    return {"message": "Router successfully shared."}

@router.delete("/{router_id}/share/{user_id}")
def revoke_share(
    router_id: int,
    user_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    if current_user.role not in (UserRole.master, UserRole.second_master):
        raise HTTPException(status_code=403, detail="Only Master or Second Master can revoke shares.")

    share = db.query(RouterShare).filter(RouterShare.router_id == router_id, RouterShare.user_id == user_id).first()
    if not share:
        raise HTTPException(status_code=404, detail="Share not found.")

    # Ensure router belongs to same tenant
    r = db.query(Router).filter(Router.id == router_id, Router.tenant_id == current_user.tenant_id).first()
    if not r:
        raise HTTPException(status_code=403, detail="Not authorized.")

    db.delete(share)
    db.commit()

    return {"message": "Router share revoked."}

@router.get("/user/{user_id}")
def list_user_shares(
    user_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    if current_user.role not in (UserRole.master, UserRole.second_master):
        raise HTTPException(status_code=403, detail="Not authorized.")

    target_user = db.query(User).filter(User.id == user_id, User.tenant_id == current_user.tenant_id).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found.")

    shares = db.query(RouterShare).filter(RouterShare.user_id == target_user.id).all()
    return [s.router_id for s in shares]

@router.get("/desktops")
def list_desktops(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    if current_user.role not in (UserRole.system_owner, UserRole.master, UserRole.second_master):
        raise HTTPException(status_code=403, detail="Not authorized")
        
    desktops = db.query(DesktopPeer).filter(
        DesktopPeer.tenant_id == current_user.tenant_id
    ).all()
    
    result = []
    for d in desktops:
        user = db.query(User).filter(User.id == d.user_id).first()
        result.append({
            "id": d.id,
            "device_name": d.device_name,
            "user_name": user.full_name if user else "Unknown",
            "user_email": user.email if user else "Unknown",
            "wg_ip": d.wg_ip,
            "active": d.active,
            "tunnel_state": d.tunnel_state,
            "last_seen": d.last_seen.isoformat() if d.last_seen else None
        })
    return result

@router.post("/{router_id}/sync")
def sync_router(
    router_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    bg_tasks: BackgroundTasks,
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
        result = claim_router(db, current_user, pv.serial_number_submitted, key_code, bg_tasks)
        pv.status = PendingValidationStatus.completed
        db.commit()
        return {"status": "claimed", "router": _router_dict(result)}
    except HTTPException as e:
        pv.status = PendingValidationStatus.failed
        pv.fail_reason = e.detail
        pv.last_sync_attempt_at = datetime.utcnow()
        db.commit()
        raise
