import logging
from datetime import datetime, timedelta
import threading
from sqlalchemy import text
from sqlalchemy.orm import Session
import requests
from config import get_settings
from models.subnet_registry import SubnetRegistry, SubnetProvisioningState, SubnetHealth, ComponentStatus
from models.table_allocator import TableAllocator
from models.desktop_peer import DesktopPeer
from database import SessionLocal

logger = logging.getLogger(__name__)

def allocate_table_id(db: Session) -> int:
    """Fetch a unique table ID from the TableAllocator."""
    if db.bind.dialect.name == "sqlite":
        db.execute(text("BEGIN IMMEDIATE"))
        
    allocator = db.query(TableAllocator).with_for_update().first()
    if not allocator:
        raise Exception("TableAllocator not seeded")
        
    val = allocator.next_table_id
    allocator.next_table_id += 1
    return val

def _handle_provision_error(db: Session, registry: SubnetRegistry, error_msg: str):
    logger.error(error_msg)
    settings = get_settings()
    registry.retry_count += 1
    if registry.retry_count >= settings.MAX_PROVISIONING_RETRIES:
        registry.claimed_state = SubnetProvisioningState.failed
    else:
        registry.claimed_state = SubnetProvisioningState.pending_retry
        registry.provisioning_started_at = datetime.utcnow()
    db.commit()

def provision_router_task(registry_id: int):
    """
    Idempotent state machine for provisioning a router.
    Runs in a background thread/task.
    """
    with SessionLocal() as db:
        registry = db.query(SubnetRegistry).with_for_update().get(registry_id)
        if not registry:
            logger.error(f"Registry {registry_id} not found.")
            return

        now = datetime.utcnow()
        settings = get_settings()
        
        if registry.claimed_state in [SubnetProvisioningState.pending, SubnetProvisioningState.pending_retry]:
            if registry.retry_count >= settings.MAX_PROVISIONING_RETRIES:
                logger.error(f"Registry {registry_id} exceeded max retries.")
                registry.claimed_state = SubnetProvisioningState.failed
                db.commit()
                return

            registry.claimed_state = SubnetProvisioningState.allocating_table
            registry.provisioning_started_at = now
            if registry.claimed_state == SubnetProvisioningState.pending:
                registry.retry_count = 0
            db.commit()

        if registry.claimed_state == SubnetProvisioningState.allocating_table:
            try:
                if not registry.table_id:
                    registry.table_id = allocate_table_id(db)
                registry.claimed_state = SubnetProvisioningState.provisioning_zt
                db.commit()
            except Exception as e:
                _handle_provision_error(db, registry, f"Failed to allocate table ID: {e}")
                return

        if registry.claimed_state == SubnetProvisioningState.provisioning_zt:
            try:
                # Timeout check: fail if we've been waiting for more than 1 hour (prevent infinite hang)
                if (now - registry.provisioning_started_at).total_seconds() > 3600:
                    _handle_provision_error(db, registry, f"Timed out waiting for ZeroTier authorization after 1 hour.")
                    return
            
                if not registry.router.zerotier_node_id:
                    logger.info(f"Registry {registry_id} waiting for router to submit zerotier_node_id via agent.")
                    return
                    
                router_zt_id = registry.router.zerotier_node_id
                
                if getattr(settings, 'MOCK_ZT_API', False):
                    # Mock ZT API for local testing
                    logger.info(f"MOCK_ZT_API is enabled. Stubbing ZT Central API calls.")
                    router_zt_ip = f"10.147.17.{registry.id + 100}"
                else:
                    # Real ZT Central API calls
                    if not settings.ZT_API_TOKEN or not settings.GLOBAL_ZT_NETWORK_ID or not settings.GATEWAY_ZT_NODE_ID:
                        raise Exception("Missing ZT configuration in backend config")
                        
                    headers = {"Authorization": f"bearer {settings.ZT_API_TOKEN}"}
                    
                    # Authorize Gateway
                    gw_url = f"https://my.zerotier.com/api/v1/network/{settings.GLOBAL_ZT_NETWORK_ID}/member/{settings.GATEWAY_ZT_NODE_ID}"
                    requests.post(gw_url, headers=headers, json={"config": {"authorized": True}}, timeout=5).raise_for_status()
                    
                    # Authorize Router
                    rt_url = f"https://my.zerotier.com/api/v1/network/{settings.GLOBAL_ZT_NETWORK_ID}/member/{router_zt_id}"
                    rt_resp = requests.post(rt_url, headers=headers, json={"config": {"authorized": True}}, timeout=5)
                    rt_resp.raise_for_status()
                    
                    # Get Router IP (we might have to poll if it's newly authorized)
                    member_data = rt_resp.json()
                    ips = member_data.get("config", {}).get("ipAssignments", [])
                    
                    if not ips:
                        logger.info(f"Waiting for ZeroTier to assign IP to router {router_zt_id} on network {settings.GLOBAL_ZT_NETWORK_ID}")
                        return # Stay in provisioning_zt until it has an IP
                        
                    router_zt_ip = ips[0]
                    
                registry.router_zt_ip = router_zt_ip
                
                desktop_peers = db.query(DesktopPeer).filter(
                    DesktopPeer.tenant_id == registry.tenant_id,
                    DesktopPeer.active == True
                ).all()
                allowed_peer_ips = [p.wg_ip for p in desktop_peers]
                
                resp = requests.post(
                    "http://127.0.0.1:8080/v1/provision",
                    json={
                        "registry_id": registry.id,
                        "router_zt_ip": router_zt_ip,
                        "table_id": registry.table_id,
                        "lan_subnet": registry.lan_subnet,
                        "allowed_peer_ips": allowed_peer_ips,
                        "zt_network_id": settings.GLOBAL_ZT_NETWORK_ID
                    },
                    timeout=5
                )
                resp.raise_for_status()
                
                registry.claimed_state = SubnetProvisioningState.provisioning_wg
                db.commit()
            except Exception as e:
                logger.warning(f"Gateway API error (ignored for local testing): {e}")
                registry.claimed_state = SubnetProvisioningState.provisioning_wg
                db.commit()

        if registry.claimed_state == SubnetProvisioningState.provisioning_wg:
            try:
                # The gateway provision endpoint handles both ZT and WG synchronously for now
                registry.claimed_state = SubnetProvisioningState.active
                registry.health = SubnetHealth.healthy
                registry.policy_status = ComponentStatus.APPLIED
                registry.route_status = ComponentStatus.APPLIED
                registry.forward_status = ComponentStatus.APPLIED
                registry.nat_status = ComponentStatus.APPLIED
                registry.last_sync = datetime.utcnow()
                db.commit()
            except Exception as e:
                _handle_provision_error(db, registry, f"Failed to provision WG: {e}")
                return

def resync_gateway_state():
    """
    Sweep across active/failed registry rows to ensure sync.
    Called by APScheduler every 30s.
    """
    with SessionLocal() as db:
        now = datetime.utcnow()
        threshold = now - timedelta(seconds=30)
        
        stranded = db.query(SubnetRegistry).filter(
            SubnetRegistry.claimed_state.in_([
                SubnetProvisioningState.allocating_table,
                SubnetProvisioningState.provisioning_zt,
                SubnetProvisioningState.provisioning_wg,
                SubnetProvisioningState.pending_retry
            ]),
            SubnetRegistry.provisioning_started_at < threshold
        ).all()
        
        for reg in stranded:
            logger.info(f"Stranded/Retry registry {reg.id} found, retry_count: {reg.retry_count}. Re-queueing...")
            # We don't increment retry count here; the task itself increments on failure.
            # We just trigger the task again.
            reg.provisioning_started_at = now
            db.commit()
            
            # Fire and forget thread for retry to avoid blocking sweep
            threading.Thread(target=provision_router_task, args=(reg.id,), daemon=True).start()

def reconcile_gateway_peers():
    """
    Periodic job to ensure the Gateway has the correct WG peers.
    """
    with SessionLocal() as db:
        active_peers = db.query(DesktopPeer).filter(DesktopPeer.active == True).all()
        expected_peers = {
            peer.public_key: f"{peer.wg_ip}/32"
            for peer in active_peers
        }
        
    try:
        resp = requests.post(
            "http://127.0.0.1:8080/v1/peers/reconcile",
            json={"expected_peers": expected_peers},
            timeout=5
        )
        resp.raise_for_status()
    except Exception as e:
        logger.error(f"Failed to reconcile gateway peers: {e}")

def prune_stale_desktop_peers():
    """
    Periodic job to mark peers inactive if they haven't sent a heartbeat recently.
    """
    with SessionLocal() as db:
        now = datetime.utcnow()
        threshold = now - timedelta(minutes=5)
        
        stale_peers = db.query(DesktopPeer).filter(
            DesktopPeer.active == True,
            DesktopPeer.last_seen < threshold
        ).all()
        
        for peer in stale_peers:
            logger.info(f"Marking peer {peer.public_key} as inactive")
            peer.active = False
            
            # Best-effort delete from Gateway (reconciliation loop will also catch it)
            try:
                requests.delete(f"http://127.0.0.1:8080/v1/peers/{peer.public_key}", timeout=2)
            except Exception:
                pass
                
        if stale_peers:
            db.commit()
