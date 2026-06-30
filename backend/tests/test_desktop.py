import pytest
from fastapi.testclient import TestClient

from models.user import User
from services.auth_service import create_access_token

def _get_headers(db_session):
    owner = db_session.query(User).filter(User.email == "owner@setulink.io").first()
    token = create_access_token({"user_id": owner.id, "uuid": owner.uuid, "role": owner.role, "tenant_id": owner.tenant_id})
    return {"Authorization": f"Bearer {token}", "X-User-Identifier": owner.uuid}

def test_desktop_register_and_rotate(client: TestClient, db_session):
    headers = _get_headers(db_session)
    
    # 1. Register new desktop peer
    res = client.post("/api/desktop/register", json={
        "public_key": "pub1",
        "device_name": "MyDesktop"
    }, headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert "wg_ip" in data
    assert "allowed_ips" in data
    
    wg_ip_1 = data["wg_ip"]
    
    # 2. Get config
    res2 = client.get("/api/desktop/config", headers=headers)
    assert res2.status_code == 200
    assert res2.json()["public_key"] == "pub1"
    assert res2.json()["active"] is True
    assert res2.json()["wg_ip"] == wg_ip_1
    
    # 3. Rotate keys (register with same device name, different public key)
    res3 = client.post("/api/desktop/register", json={
        "public_key": "pub2",
        "device_name": "MyDesktop"
    }, headers=headers)
    assert res3.status_code == 200
    assert res3.json()["wg_ip"] == wg_ip_1 # Should preserve wg_ip
    
    # Verify config updated
    res4 = client.get("/api/desktop/config", headers=headers)
    assert res4.status_code == 200
    assert res4.json()["public_key"] == "pub2"

def test_desktop_disconnect(client: TestClient, db_session):
    headers = _get_headers(db_session)
    
    # Register
    client.post("/api/desktop/register", json={
        "public_key": "pub3",
        "device_name": "DisconnectTest"
    }, headers=headers)
    
    # Disconnect
    res = client.post("/api/desktop/disconnect", json={
        "public_key": "pub3"
    }, headers=headers)
    assert res.status_code == 200
    
    # Verify config shows inactive
    res2 = client.get("/api/desktop/config", headers=headers)
    assert res2.status_code == 200
    assert res2.json()["active"] is False

def test_list_desktops(client: TestClient, db_session):
    headers = _get_headers(db_session)
    
    # Register 2 peers
    client.post("/api/desktop/register", json={"public_key": "pub_list1", "device_name": "D1"}, headers=headers)
    client.post("/api/desktop/register", json={"public_key": "pub_list2", "device_name": "D2"}, headers=headers)
    
    # Fetch list
    res = client.get("/api/routers/desktops", headers=headers)
    assert res.status_code == 200
    desktops = res.json()
    
    assert len([d for d in desktops if d["device_name"] in ("D1", "D2")]) == 2
    for d in desktops:
        if d["device_name"] == "D1":
            assert d["user_name"] == "System Owner"
            assert d["tunnel_state"] == "connected"
