from fastapi import FastAPI, HTTPException, Header, Depends
from pydantic import BaseModel
from typing import List
import logging
import os
import json
from network.wg import WireGuardManager
from network.zt import ZeroTierManager
from network.routing import RoutingManager

async def verify_token(x_gateway_token: str = Header(default="")):
    expected_token = os.getenv("GATEWAY_API_TOKEN", "default-gateway-token-12345")
    if x_gateway_token != expected_token:
        raise HTTPException(status_code=401, detail="Invalid Gateway Token")

STATE_FILE = "gateway_state.json"

def _load_state() -> dict:
    # Note: File-based state has concurrency limitations under heavy load.
    # We use this for simplicity, but a real database (SQLite/Redis) would be needed if traffic scales.
    if not os.path.exists(STATE_FILE):
        return {}
    try:
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {}

def _save_state(state: dict):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)

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

@app.post("/v1/provision", dependencies=[Depends(verify_token)])
def provision(req: ProvisionRequest):
    try:
        logger.info(f"Provisioning request for registry {req.registry_id}")
        
        # Join ZeroTier network (or just get the interface if already joined)
        zt_interface = zt.join_network(req.zt_network_id)
        
        # Flush the old routing table to ensure no stale rules accumulate
        routing.flush_table(req.table_id)
        
        # Apply routing for all allowed WG peers
        for peer_ip in req.allowed_peer_ips:
            routing.add_policy_route(peer_ip, req.lan_subnet, req.table_id, zt_interface, req.router_zt_ip)
            
        state = _load_state()
        state[str(req.registry_id)] = {
            "zt_network_id": req.zt_network_id,
            "table_id": req.table_id,
            "lan_subnet": req.lan_subnet,
            "allowed_peer_ips": req.allowed_peer_ips,
            "zt_interface": zt_interface
        }
        _save_state(state)
            
        return {"status": "ok", "registry_id": req.registry_id, "zt_interface": zt_interface}
    except Exception as e:
        logger.error(f"Provisioning failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/v1/deprovision/{registry_id}", dependencies=[Depends(verify_token)])
def deprovision(registry_id: int):
    try:
        state = _load_state()
        str_id = str(registry_id)
        if str_id not in state:
            return {"status": "ok", "message": "already deprovisioned"}
            
        data = state[str_id]
        
        # Clean up routing rules
        for peer_ip in data.get("allowed_peer_ips", []):
            routing.remove_policy_route(peer_ip, data["lan_subnet"], data["table_id"], data["zt_interface"])
            
        routing.flush_table(data["table_id"])
        
        del state[str_id]
        _save_state(state)
        
        return {"status": "ok", "registry_id": registry_id}
    except Exception as e:
        logger.error(f"Deprovisioning failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

class PeerRequest(BaseModel):
    public_key: str
    allowed_ips: str

class ReconcilePeersRequest(BaseModel):
    expected_peers: dict[str, str]

@app.post("/v1/peers", dependencies=[Depends(verify_token)])
def add_peer(req: PeerRequest):
    try:
        wg.ensure_peer(req.public_key, req.allowed_ips)
        return {"status": "ok", "public_key": req.public_key}
    except Exception as e:
        logger.error(f"Failed to add peer: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/v1/peers/{public_key}", dependencies=[Depends(verify_token)])
def delete_peer(public_key: str):
    try:
        wg.remove_peer(public_key)
        return {"status": "ok", "public_key": public_key}
    except Exception as e:
        logger.error(f"Failed to remove peer: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/v1/peers/reconcile", dependencies=[Depends(verify_token)])
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
