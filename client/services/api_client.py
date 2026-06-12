import httpx
from typing import Optional
# pyrefly: ignore [missing-import]
from config import BACKEND_URL


class APIClient:
    def __init__(self):
        self.token: Optional[str] = None
        self.base = BACKEND_URL
        self._client = httpx.Client(
            timeout=10.0,
            limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
        )

    def _headers(self) -> dict:
        h = {"Content-Type": "application/json"}
        if self.token:
            h["Authorization"] = f"Bearer {self.token}"
        return h

    def _req(self, method: str, path: str, **kwargs):
        url = self.base + path
        resp = self._client.request(method, url, headers=self._headers(), **kwargs)
        resp.raise_for_status()
        return resp.json()

    # ── Auth ──────────────────────────────────────────────────────
    def login(self, email: str, password: str) -> dict:
        data = self._req("POST", "/api/auth/login", json={"email": email, "password": password})
        self.token = data["access_token"]
        self._password = password
        return data

    def _queue_offline_action(self, action: str, payload: dict):
        import json
        from pathlib import Path
        queue_file = Path.home() / ".projectx" / "offline_queue.json"
        queue_file.parent.mkdir(parents=True, exist_ok=True)
        queue = []
        if queue_file.exists():
            try:
                queue = json.loads(queue_file.read_text())
            except Exception:
                pass
        queue.append({"action": action, "payload": payload})
        queue_file.write_text(json.dumps(queue))

    def sync_offline_queue(self):
        import json
        from pathlib import Path
        import httpx
        queue_file = Path.home() / ".projectx" / "offline_queue.json"
        if not queue_file.exists():
            return
        try:
            queue = json.loads(queue_file.read_text())
        except Exception:
            return
        
        remaining = []
        for item in queue:
            try:
                action = item.get("action")
                payload = item.get("payload", {})
                if action == "rename_device":
                    self._req("PATCH", f"/api/devices/{payload['device_id']}/rename", json={"name": payload['name']})
                elif action == "rename_lan_device":
                    self._req("PATCH", f"/api/lan-devices/{payload['lan_device_id']}/rename", json={"name": payload['name']})
            except httpx.ConnectError:
                remaining.append(item)
            except Exception as e:
                print(f"Failed to sync offline action {item}: {e}")
                
        if remaining:
            queue_file.write_text(json.dumps(remaining))
        else:
            queue_file.unlink(missing_ok=True)

    def get_me(self) -> dict:
        user = self._req("GET", "/api/auth/me")
        self._user = user
        return user

    def setup_2fa(self) -> dict:
        return self._req("POST", "/api/auth/setup-2fa")

    def verify_2fa(self, code: str) -> dict:
        return self._req("POST", "/api/auth/verify-2fa", json={"code": code})

    def activate_key(self, key_code: str, email: str, full_name: str, password: str) -> dict:
        data = self._req("POST", "/api/auth/activate-key", json={
            "key_code": key_code, "email": email,
            "full_name": full_name, "password": password,
        })
        self.token = data["access_token"]
        return data

    def claim_network(self, network_id: str) -> dict:
        return self._req("POST", "/api/auth/claim-network", json={"network_id": network_id})

    def claim_wg_server(self, server_public_key: str, server_endpoint: str, interface: str = "wg0") -> dict:
        return self._req("POST", "/api/auth/claim-wg-server", json={
            "server_public_key": server_public_key,
            "server_endpoint": server_endpoint,
            "server_interface": interface
        })

    def get_wg_tunnel_peers(self) -> dict:
        return self._req("GET", "/api/devices/wg-tunnel-peers")

    def change_password(self, new_password: str) -> dict:
        return self._req("POST", "/api/auth/change-password", json={"new_password": new_password})

    # ── Owner / Admin ─────────────────────────────────────────────
    def force_2fa_all(self) -> dict:
        return self._req("POST", "/api/admin/force-2fa-all")

    def get_admin_stats(self) -> dict:
        return self._req("GET", "/api/admin/stats")

    def get_admin_tenants(self) -> list:
        return self._req("GET", "/api/admin/tenants")

    def create_tenant(self, company_name: str, city: str = "") -> dict:
        return self._req("POST", "/api/admin/tenants", json={"company_name": company_name, "city": city})

    def update_tenant(self, tenant_id: int, max_second_masters: int) -> dict:
        return self._req("PATCH", f"/api/admin/tenants/{tenant_id}", json={"max_second_masters": max_second_masters})

    # pyrefly: ignore [bad-function-definition]
    def delete_tenant(self, tenant_id: int, totp_code: str = None) -> dict:
        url = f"/api/admin/tenants/{tenant_id}"
        if totp_code:
            url += f"?totp_code={totp_code}"
        return self._req("DELETE", url)

    def get_admin_keys(self) -> list:
        return self._req("GET", "/api/admin/keys")

    def generate_key(self, tenant_id: int) -> dict:
        return self._req("POST", f"/api/admin/keys?tenant_id={tenant_id}")

    def delete_key(self, key_id: int) -> dict:
        return self._req("DELETE", f"/api/admin/keys/{key_id}")

    def get_admin_audit_logs(self, from_date: str = None, to_date: str = None) -> list:
        url = "/api/admin/audit-logs"
        params = []
        if from_date: params.append(f"from_date={from_date}")
        if to_date: params.append(f"to_date={to_date}")
        if params: url += "?" + "&".join(params)
        return self._req("GET", url)

    def get_admin_users(self) -> list:
        return self._req("GET", "/api/admin/users")

    # ── Devices ───────────────────────────────────────────────────
    def get_devices(self) -> list:
        try:
            self.sync_offline_queue()
        except Exception:
            pass
        devices = self._req("GET", "/api/devices/")
        
        # Save to offline cache
        # pyrefly: ignore [missing-import]
        from services.cache_service import cache_service
        pwd = getattr(self, "_password", None)
        usr = getattr(self, "_user", None)
        if pwd and usr and self.token:
            try:
                cache_service.save({
                    "token": self.token,
                    "user": usr,
                    "devices": devices
                }, pwd)
            except Exception as e:
                print(f"Failed to save cache: {e}")
                
        return devices

    def get_pending_devices(self) -> list:
        return self._req("GET", "/api/devices/pending")

    def approve_device(self, device_id: int) -> dict:
        return self._req("POST", f"/api/devices/{device_id}/approve")

    # pyrefly: ignore [bad-function-definition]
    def remove_device(self, device_id: int, totp_code: str = None) -> dict:
        url = f"/api/devices/{device_id}"
        if totp_code:
            url += f"?totp_code={totp_code}"
        return self._req("DELETE", url)

    def rename_device(self, device_id: int, name: str) -> dict:
        try:
            return self._req("PATCH", f"/api/devices/{device_id}/rename", json={"name": name})
        except httpx.ConnectError:
            self._queue_offline_action("rename_device", {"device_id": device_id, "name": name})
            return {"message": "Queued for offline sync"}

    def get_lan_devices(self, device_id: int) -> list:
        return self._req("GET", f"/api/lan-devices/{device_id}")

    def rename_lan_device(self, lan_device_id: int, name: str) -> dict:
        try:
            return self._req("PATCH", f"/api/lan-devices/{lan_device_id}/rename", json={"name": name})
        except httpx.ConnectError:
            self._queue_offline_action("rename_lan_device", {"lan_device_id": lan_device_id, "name": name})
            return {"message": "Queued for offline sync"}

    # ── Users ─────────────────────────────────────────────────────
    def get_users(self) -> list:
        return self._req("GET", "/api/users/")

    def create_user(self, email: str, full_name: str, role: str, password: str = "") -> dict:
        body = {"email": email, "full_name": full_name, "role": role}
        if password:
            body["password"] = password
        return self._req("POST", "/api/users/", json=body)

    # pyrefly: ignore [bad-function-definition]
    def delete_user(self, user_id: int, totp_code: str = None) -> dict:
        url = f"/api/users/{user_id}"
        if totp_code:
            url += f"?totp_code={totp_code}"
        return self._req("DELETE", url)

    # pyrefly: ignore [bad-function-definition]
    def remove_user(self, user_id: int, totp_code: str = None) -> dict:
        return self.delete_user(user_id, totp_code)

    # pyrefly: ignore [bad-function-definition]
    def demote_user(self, user_id: int, totp_code: str = None) -> dict:
        url = f"/api/users/{user_id}/role"
        if totp_code:
            url += f"?totp_code={totp_code}"
        return self._req("PATCH", url, json={"new_role": "admin"})

    def toggle_trust(self, user_id: int, is_trusted: bool) -> dict:
        return self._req("PATCH", f"/api/users/{user_id}/trust", json={"is_trusted": is_trusted})

    # ── Devices ───────────────────────────────────────────────────
    # pyrefly: ignore [bad-function-definition]
    def register_device(self, node_id: str, network_id: str, zt_ip: str = None, lan_ip: str = None, hostname: str = "Unknown Device", lan_subnet: str = None) -> dict:
        body = {"zerotier_node_id": node_id, "network_id": network_id, "hostname": hostname}
        if zt_ip:
            body["zerotier_ip"] = zt_ip
        if lan_ip:
            body["lan_ip"] = lan_ip
        if lan_subnet:
            body["lan_subnet"] = lan_subnet
        return self._req("POST", "/api/devices/register", json=body)

    # pyrefly: ignore [bad-function-definition]
    def send_heartbeat(self, node_id: str, network_id: str, zt_ip: str = None, lan_ip: str = None, hostname: str = None, lan_subnet: str = None) -> dict:
        body = {"zerotier_node_id": node_id, "network_id": network_id}
        if zt_ip:
            body["zerotier_ip"] = zt_ip
        if lan_ip:
            body["lan_ip"] = lan_ip
        if hostname:
            body["hostname"] = hostname
        if lan_subnet:
            body["lan_subnet"] = lan_subnet
        return self._req("POST", "/api/devices/heartbeat", json=body)

    def toggle_force_2fa(self, user_id: int, force_2fa: bool) -> dict:
        return self._req("PATCH", f"/api/users/{user_id}/force-2fa", json={"force_2fa": force_2fa})

    def get_user_assigned_devices(self, user_id: int) -> list[int]:
        return self._req("GET", f"/api/users/{user_id}/assigned-devices")

    def assign_devices(self, user_id: int, device_ids: list[int]) -> dict:
        current = set(self.get_user_assigned_devices(user_id))
        target = set(device_ids)
        for cid in current - target:
            self._req("DELETE", f"/api/users/{user_id}/assign-device/{cid}")
        for did in target - current:
            self._req("POST", f"/api/users/{user_id}/assign-device", json={"device_id": did})
        return {"message": "Devices updated"}

    def sync_lan_devices(self, device_id: int, devices: list) -> dict:
        return self._req("POST", f"/api/lan-devices/{device_id}/sync", json={"devices": devices})

    def sync_device_toggle(self, device_id: int, network_id: str, connect: bool) -> dict:
        return self._req("POST", f"/api/devices/{device_id}/sync-toggle", json={"connect": connect, "network_id": network_id})

    def change_network_mode(self, device_id: int, is_layer2: bool) -> dict:
        return self._req("POST", f"/api/devices/{device_id}/network-mode", json={"is_layer2": is_layer2})

    def get_device_shares(self, device_id: int) -> list:
        return self._req("GET", f"/api/device-shares/device/{device_id}")

    def create_device_share(self, device_id: int, target_tenant_id: int) -> dict:
        return self._req("POST", "/api/device-shares", json={"device_id": device_id, "target_tenant_id": target_tenant_id})

    def revoke_device_share(self, share_id: int) -> dict:
        return self._req("DELETE", f"/api/device-shares/{share_id}")

    # ── Audit ─────────────────────────────────────────────────────
    def get_audit_logs(self, from_date: str = None, to_date: str = None) -> list:
        url = "/api/audit/"
        params = []
        if from_date: params.append(f"from_date={from_date}")
        if to_date: params.append(f"to_date={to_date}")
        if params: url += "?" + "&".join(params)
        return self._req("GET", url)
        
    def export_audit_logs(self) -> str:
        with httpx.Client(base_url=self.base) as client:
            r = client.get("/api/admin/audit/export", headers=self._headers())
            r.raise_for_status()
            return r.text

api = APIClient()
