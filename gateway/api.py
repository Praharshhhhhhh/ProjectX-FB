from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List
import logging
from network.wg import WireGuardManager
from network.zt import ZeroTierManager
from network.routing import RoutingManager

app = FastAPI(title="SetuLink Gateway Daemon")
logger = logging.getLogger(__name__)

wg = WireGuardManager()
zt = ZeroTierManager()
routing = RoutingManager()

class ProvisionRequest(BaseModel):
    registry_id: int
    router_zt_ip: str
    zt_network_id: str
    table_id: int
    lan_subnet: str
    allowed_peer_ips: List[str] = []

@app.post("/v1/provision")
def provision(req: ProvisionRequest):
    try:
        logger.info(f"Provisioning request for registry {req.registry_id}")
        
        # Join ZeroTier network (or just get the interface if already joined)
        zt_interface = zt.join_network(req.zt_network_id)
        
        # Apply routing for all allowed WG peers
        for peer_ip in req.allowed_peer_ips:
            routing.add_policy_route(peer_ip, req.lan_subnet, req.table_id, zt_interface, req.router_zt_ip)
            
        return {"status": "ok", "registry_id": req.registry_id, "zt_interface": zt_interface}
    except Exception as e:
        logger.error(f"Provisioning failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/v1/deprovision/{registry_id}")
def deprovision(registry_id: int):
    # TODO: need full payload or store state locally to properly teardown
    # For now, this is a placeholder. 
    return {"status": "ok", "registry_id": registry_id}

class PeerRequest(BaseModel):
    public_key: str
    allowed_ips: str

class ReconcilePeersRequest(BaseModel):
    expected_peers: dict[str, str]

@app.post("/v1/peers")
def add_peer(req: PeerRequest):
    try:
        wg.ensure_peer(req.public_key, req.allowed_ips)
        return {"status": "ok", "public_key": req.public_key}
    except Exception as e:
        logger.error(f"Failed to add peer: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/v1/peers/{public_key}")
def delete_peer(public_key: str):
    try:
        wg.remove_peer(public_key)
        return {"status": "ok", "public_key": public_key}
    except Exception as e:
        logger.error(f"Failed to remove peer: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/v1/peers/reconcile")
def reconcile_peers(req: ReconcilePeersRequest):
    try:
        wg.reconcile_peers(req.expected_peers)
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"Failed to reconcile peers: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/v1/health")
def health():
    # TODO: return reconciliation state
    return {"status": "healthy"}
