import httpx
from typing import Optional
from config import BACKEND_URL


class TokenExpiredOfflineError(Exception):
    pass


class APIClient:
    def __init__(self):
        self.token: Optional[str] = None
        self.base = BACKEND_URL
        self.last_cached_at = 0
        self.is_offline = False
        self._client = httpx.Client(
            timeout=10.0,
            limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
            follow_redirects=True,
        )

    def _headers(self) -> dict:
        h = {"Content-Type": "application/json"}
        if self.token:
            h["Authorization"] = f"Bearer {self.token}"
        if getattr(self, "_user_uuid", None):
            h["X-User-Identifier"] = self._user_uuid
        return h

    def _req(self, method: str, path: str, **kwargs):
        url = self.base + path
        try:
            resp = self._client.request(method, url, headers=self._headers(), **kwargs)
            resp.raise_for_status()
            self.is_offline = False
            data = resp.json()
            if method == "GET":
                from services.cache_service import cache_service
                cache_service.set_cache(path, data)
            self.last_cached_at = 0
            return data
        except (httpx.RequestError, OSError) as e:
            self.is_offline = True
            if method == "GET":
                from services.cache_service import cache_service
                data, cached_at = cache_service.get_cache(path)
                if data is not None:
                    self.last_cached_at = cached_at
                    return data
            raise

    # ── Auth ──────────────────────────────────────────────────────
    def login(self, email: str, password: str) -> dict:
        self._user_uuid = None
        data = self._req("POST", "/api/auth/login", json={"email": email, "password": password})
        # If OTP is not required, set the token immediately
        if not data.get("requires_otp"):
            self.token = data.get("access_token")
        self._password = password
        return data

    def verify_otp(self, email: str, code: str) -> dict:
        data = self._req("POST", "/api/auth/verify-otp", json={"email": email, "code": code})
        self.token = data.get("access_token")
        return data

    def resend_otp(self, email: str) -> dict:
        return self._req("POST", "/api/auth/resend-otp", json={"email": email})

    def logout(self):
        self.token = None
        self._user_uuid = None
        self._password = None
        self._user = None

    def _queue_offline_action(self, action: str, payload: dict):
        from services.cache_service import cache_service
        cache_service.add_offline_action(action, payload)

    def sync_offline_queue(self):
        from services.cache_service import cache_service
        actions = cache_service.get_offline_actions()
        if not actions:
            return
        
        for item in actions:
            action_id = item["id"]
            action = item["action"]
            payload = item["payload"]
            try:
                if action == "claim_router":
                    self._req("POST", "/api/routers/claim", json={
                        "serial_number": payload["serial_number"],
                        "activation_key": payload["activation_key"]
                    })
                elif action == "rename_router":
                    self._req("PATCH", f"/api/routers/{payload['router_id']}/rename", json={
                        "name": payload["name"]
                    })
                elif action == "sync_router":
                    self._req("POST", f"/api/routers/{payload['router_id']}/sync")
                elif action == "share_router":
                    self._req("POST", f"/api/routers/{payload['router_id']}/share")
                elif action == "change_password":
                    self._req("POST", "/api/auth/change-password", json={
                        "new_password": payload["new_password"]
                    })
                
                cache_service.remove_offline_action(action_id)
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 401:
                    cache_service.remove_offline_action(action_id)
                else:
                    print(f"Server rejected offline action {item}: {e}")
                    cache_service.remove_offline_action(action_id)
            except (httpx.RequestError, OSError):
                # Still offline
                break
            except Exception as e:
                print(f"Failed to sync offline action {item}: {e}")

    def get_me(self) -> dict:
        user = self._req("GET", "/api/auth/me")
        self._user = user
        self._user_uuid = user.get("uuid")
        return user

    def activate_key(self, key_code: str, email: str, full_name: str, password: str) -> dict:
        data = self._req("POST", "/api/auth/activate-key", json={
            "key_code": key_code, "email": email,
            "full_name": full_name, "password": password,
        })
        self.token = data["access_token"]
        return data

    def change_password(self, new_password: str) -> dict:
        try:
            res = self._req("POST", "/api/auth/change-password", json={"new_password": new_password})
            from services.cache_service import cache_service
            auth_data, _ = cache_service.get_cache("_offline_auth")
            if auth_data:
                auth_data["password"] = new_password
                cache_service.set_cache("_offline_auth", auth_data)
            return res
        except (httpx.RequestError, OSError):
            self._queue_offline_action("change_password", {"new_password": new_password})
            from services.cache_service import cache_service
            auth_data, _ = cache_service.get_cache("_offline_auth")
            if auth_data:
                auth_data["password"] = new_password
                cache_service.set_cache("_offline_auth", auth_data)
            return {"message": "Queued for offline sync"}

    # ── Routers ───────────────────────────────────────────────────
    def get_routers(self) -> list:
        try:
            self.sync_offline_queue()
        except Exception:
            pass
        return self._req("GET", "/api/routers/")

    def claim_router(self, serial_number: str, activation_key: str) -> dict:
        try:
            return self._req("POST", "/api/routers/claim", json={
                "serial_number": serial_number,
                "activation_key": activation_key
            })
        except (httpx.RequestError, OSError):
            # Cache locally for offline queue replay
            self._queue_offline_action("claim_router", {
                "serial_number": serial_number,
                "activation_key": activation_key
            })
            
            # Construct a mock pending validation router in local endpoint cache
            from services.cache_service import cache_service
            routers, _ = cache_service.get_cache("/api/routers")
            if routers is None:
                routers = []
            
            import uuid
            mock_id = int(uuid.uuid4().int >> 96)
            routers.append({
                "id": mock_id,
                "router_id": "Offline-Prep",
                "serial_number": serial_number,
                "mac_address": "unknown",
                "status": "pending_validation",
                "name": f"Pending Claim: {serial_number}"
            })
            cache_service.set_cache("/api/routers", routers)
            
            return {"message": "Claim queued offline", "status": "pending_validation"}

    def rename_router(self, router_id: int, name: str) -> dict:
        try:
            return self._req("PATCH", f"/api/routers/{router_id}/rename", json={"name": name})
        except (httpx.RequestError, OSError):
            self._queue_offline_action("rename_router", {"router_id": router_id, "name": name})
            from services.cache_service import cache_service
            data, _ = cache_service.get_cache("/api/routers")
            if data and isinstance(data, list):
                for r in data:
                    if r.get("id") == router_id:
                        r["name"] = name
                        break
                cache_service.set_cache("/api/routers", data)
            return {"message": "Rename queued offline"}

    def sync_router(self, router_id: int) -> dict:
        try:
            return self._req("POST", f"/api/routers/{router_id}/sync")
        except (httpx.RequestError, OSError):
            self._queue_offline_action("sync_router", {"router_id": router_id})
            return {"message": "Sync queued offline"}

    def share_router(self, router_id: int) -> dict:
        try:
            return self._req("POST", f"/api/routers/{router_id}/share")
        except (httpx.RequestError, OSError):
            self._queue_offline_action("share_router", {"router_id": router_id})
            return {"message": "Share queued offline"}

    # ── Owner / Admin ─────────────────────────────────────────────
    def get_admin_stats(self) -> dict:
        return self._req("GET", "/api/admin/stats")

    def get_admin_tenants(self) -> list:
        return self._req("GET", "/api/admin/tenants")

    def create_tenant(self, company_name: str, master_email: str) -> dict:
        return self._req("POST", "/api/admin/tenants", json={
            "company_name": company_name,
            "master_email": master_email
        })

    def delete_tenant(self, tenant_id: int) -> dict:
        return self._req("DELETE", f"/api/admin/tenants/{tenant_id}")

    def get_pending_keys(self) -> list:
        return self._req("GET", "/api/admin/pending-keys")

    def resend_activation_key(self, key_id: int, recipient_email: str) -> dict:
        return self._req("POST", f"/api/admin/pending-keys/{key_id}/resend",
                         json={"recipient_email": recipient_email})

    def get_all_activation_keys(self) -> list:
        return self._req("GET", "/api/admin/activation-keys")

    def delete_activation_key(self, key_id: int) -> dict:
        return self._req("DELETE", f"/api/admin/activation-keys/{key_id}")

    def force_2fa_all(self) -> dict:
        return self._req("PATCH", "/api/admin/force-otp-all")

    def get_admin_users(self) -> list:
        return self._req("GET", "/api/admin/users")

    def prepare_router(self, router_id: str, serial_number: str, mac_address: str, recipient_email: str, zerotier_node_id: str = "") -> dict:
        return self._req("POST", "/api/admin/routers/prepare", json={
            "router_id": router_id,
            "serial_number": serial_number,
            "mac_address": mac_address,
            "recipient_email": recipient_email,
            "zerotier_node_id": zerotier_node_id
        })

    def activate_master_account(self, key_code: str, email: str, full_name: str, password: str) -> dict:
        return self._req("POST", "/api/auth/activate-master", json={
            "key_code": key_code,
            "email": email,
            "full_name": full_name,
            "password": password
        })

    def get_users(self) -> list:
        return self._req("GET", "/api/users/")

    def create_user(self, email: str, full_name: str, role: str) -> dict:
        return self._req("POST", "/api/users/", json={
            "email": email,
            "full_name": full_name,
            "role": role,
            "password": ""  # Backend generates a temp password if empty
        })

    def delete_user(self, user_id: int) -> dict:
        return self._req("DELETE", f"/api/users/{user_id}")

    def update_user(self, user_id: int, updates: dict) -> dict:
        return self._req("PATCH", f"/api/users/{user_id}", json=updates)

    def toggle_trust(self, user_id: int, is_trusted: bool) -> dict:
        return self._req("PATCH", f"/api/users/{user_id}/trust", json={"is_trusted": is_trusted})

    def toggle_force_otp(self, user_id: int, force_2fa: bool) -> dict:
        return self._req("PATCH", f"/api/users/{user_id}/force-2fa", json={"force_2fa": force_2fa})

    def update_user_role(self, user_id: int, new_role: str) -> dict:
        return self._req("PATCH", f"/api/users/{user_id}/role", json={"new_role": new_role})


api = APIClient()
