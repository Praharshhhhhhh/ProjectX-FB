import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from PyQt6.QtWidgets import QApplication
# pyrefly: ignore [missing-import]
from services.api_client import api
# pyrefly: ignore [missing-import]
from windows.login_window import LoginWindow
# pyrefly: ignore [missing-import]
from windows.activate_key_window import ActivateKeyWindow
# pyrefly: ignore [missing-import]
from windows.setup_2fa_window import Setup2FAWindow
# pyrefly: ignore [missing-import]
from windows.claim_network_window import ClaimNetworkWindow
# pyrefly: ignore [missing-import]
from windows.main_window import MainWindow
# pyrefly: ignore [missing-import]
from windows.owner_window import OwnerWindow
# pyrefly: ignore [missing-import]
from windows.home_window import HomeWindow
# pyrefly: ignore [missing-import]
from config import APP_NAME


class App:
    def __init__(self):
        self.qt_app = QApplication(sys.argv)
        self.qt_app.setApplicationName(APP_NAME)
        self.qt_app.setStyle("Fusion")
        self._token_data = {}
        self._user_info  = {}
        
        # pyrefly: ignore [missing-import]
        from windows.root_window import RootWindow
        self.root = RootWindow()
        
        self._show_login()

    # ── Home ──────────────────────────────────────────────────────
    def _show_home(self):
        self._home = HomeWindow()
        self._home.goto_login.connect(self._show_login)
        self._home.goto_activate.connect(self._show_activate_from_home)
        self.root.set_view(self._home)

    # ── Login ─────────────────────────────────────────────────────
    def _show_login(self):
        self._login = LoginWindow(api)
        self._login.login_success.connect(self._on_login_success)
        self._login.goto_activate.connect(self._show_activate)
        self.root.set_view(self._login)

    def _show_activate_from_home(self):
        self._show_activate()

    def _show_activate(self):
        self._activate = ActivateKeyWindow(api)
        self._activate.activation_success.connect(self._on_activation_success)
        self._activate.goto_login.connect(self._back_to_login)
        self.root.set_view(self._activate)

    def _back_to_login(self):
        self._show_login()

    def _on_login_success(self, token_data: dict, me: dict):
        self._token_data = token_data
        self._user_info  = me
        
        role = me.get("role")
        if role != "system_owner":
            # pyrefly: ignore [missing-import]
            from services.websocket_client import ws_client
            ws_client.connect_ws(api.base, token_data.get("access_token"))
            
            try:
                ws_client.mesh_updated.disconnect(self._on_mesh_updated)
                ws_client.device_removed.disconnect(self._on_mesh_updated)
                ws_client.device_updated.disconnect(self._on_mesh_updated)
            except TypeError:
                pass
            ws_client.mesh_updated.connect(self._on_mesh_updated)
            ws_client.device_removed.connect(self._on_mesh_updated)
            ws_client.device_updated.connect(self._on_mesh_updated)
            
        if token_data.get("requires_2fa") and not me.get("totp_enabled"):
            self._show_2fa_setup()
        else:
            role = me.get("role")
            from config import TUNNEL_MODE
            if TUNNEL_MODE == "zerotier" and role in ("master", "second_master") and not me.get("network_id"):
                self._show_claim_network()
            else:
                self._show_main()

    def _on_activation_success(self, token_data: dict):
        self._token_data = token_data
        self._show_2fa_setup()

    # ── 2FA / Claim ───────────────────────────────────────────────
    def _show_2fa_setup(self):
        self._setup2fa = Setup2FAWindow(api)
        self._setup2fa.setup_complete.connect(self._after_2fa)
        self.root.set_view(self._setup2fa)

    def _after_2fa(self):
        self._user_info = api.get_me()
        role = self._user_info.get("role")
        from config import TUNNEL_MODE
        if TUNNEL_MODE == "zerotier" and role in ("master", "second_master") and not self._user_info.get("network_id"):
            self._show_claim_network()
        else:
            self._show_main()

    def _show_claim_network(self):
        self._claim = ClaimNetworkWindow(api)
        self._claim.claim_success.connect(self._show_main)
        self.root.set_view(self._claim)

    def _on_mesh_updated(self, *args):
        pass
    

    # ── Main portal ───────────────────────────────────────────────
    def _show_main(self):
        self._user_info = api.get_me()

        network_id = self._user_info.get("network_id")
        
        # pyrefly: ignore [missing-import]
        from config import TUNNEL_MODE
        if TUNNEL_MODE == "wireguard":
            # pyrefly: ignore [missing-import]
            from services import wireguard_local as tunnel
        else:
            # pyrefly: ignore [missing-import]
            from services import zerotier_local as tunnel

        role = self._user_info.get("role")
        has_wg_server = self._user_info.get("has_wg_server")

        if network_id or TUNNEL_MODE == "wireguard":
            import threading
            import socket
            import time

            if TUNNEL_MODE == "wireguard":
                # Always register with backend to ensure config and tenant are in sync
                try:
                    # pyrefly: ignore [missing-import]
                    from services.network_monitor import _get_active_interface
                    lan_ip = _get_active_interface()
                    existing_priv, existing_pub = tunnel.get_or_create_keypair()
                    req_data = {
                        "hostname": socket.gethostname(),
                        "lan_ip": lan_ip
                    }
                    if existing_pub:
                        req_data["wg_public_key"] = existing_pub
                        
                    res = api._req("POST", "/api/devices/wg-register", json=req_data)
                    config_str = res.get("config")
                    assigned_ip = res.get("assigned_ip")
                    server_pubkey = res.get("server_pubkey")
                    server_endpoint = res.get("server_endpoint")
                    server_endpoint_secondary = res.get("server_endpoint_secondary")
                    priv = res.get("private_key") or existing_priv
                    device_id = res.get("device_id")
                    
                    if server_pubkey and assigned_ip and priv:
                        import os
                        # pyrefly: ignore [missing-import]
                        from config import WG_CONFIG_DIR, WG_INTERFACE
                        config_path = os.path.join(WG_CONFIG_DIR, f"{WG_INTERFACE}.conf")
                        
                        was_running = tunnel.is_wireguard_running()
                        
                        listen_port = 51820
                        pub_ip, pub_port = tunnel.discover_stun(listen_port)
                        if pub_ip and pub_port:
                            print(f"STUN Discovered Endpoint: {pub_ip}:{pub_port}")
                            # WireGuard handles endpoint updating automatically via incoming packets + PersistentKeepalive
                            
                        config_changed = tunnel.write_config(priv, assigned_ip, server_pubkey, server_endpoint, config_path)
                        
                        import json
                        failover_path = os.path.join(WG_CONFIG_DIR, "failover.json")
                        if server_endpoint_secondary:
                            with open(failover_path, "w") as f:
                                json.dump({
                                    "primary": server_endpoint,
                                    "secondary": server_endpoint_secondary,
                                    "current": "primary",
                                    "priv": priv,
                                    "assigned_ip": assigned_ip,
                                    "server_pubkey": server_pubkey
                                }, f)
                        else:
                            if os.path.exists(failover_path):
                                os.remove(failover_path)

                        if config_changed:
                            if was_running:
                                tunnel.disconnect(WG_INTERFACE)
                            tunnel.connect(WG_INTERFACE, assigned_ip)
                        elif not was_running:
                            tunnel.connect(WG_INTERFACE, assigned_ip)
                    else:
                        print("WireGuard registration error: Backend did not return valid details. (Is the wg0 interface running on the server?)")
                except Exception as e:
                    print("WireGuard registration failed:", e)
    
                priv, pub = tunnel.get_or_create_keypair()
                node_id = pub
            else:
                if tunnel.is_zerotier_running():
                    node_info = tunnel.get_node_info()
                    node_id = node_info.get("address")
                else:
                    node_id = None
    
            if node_id:
                def _do_heartbeat():
                    try:
                        tun_ip = tunnel.get_network_ip(network_id) if not TUNNEL_MODE == "wireguard" else ""
                        if TUNNEL_MODE != "wireguard":
                            api.register_device(node_id, network_id, zt_ip=tun_ip, hostname=socket.gethostname())
                    except Exception:
                        pass
                    while True:
                        try:
                            # pyrefly: ignore [missing-import]
                            from services.network_monitor import _get_active_interface
                            lan_ip = _get_active_interface()
                            
                            if TUNNEL_MODE == "wireguard":
                                # pyrefly: ignore [missing-import]
                                from config import WG_INTERFACE
                                target_id = WG_INTERFACE
                            else:
                                target_id = network_id
    
                            tun_ip = tunnel.get_network_ip(target_id)
                            tun_status = tunnel.get_status(target_id)
                            
                            if tun_status == "disconnected" and TUNNEL_MODE == "wireguard":
                                import os, json
                                from config import WG_CONFIG_DIR, WG_INTERFACE
                                failover_path = os.path.join(WG_CONFIG_DIR, "failover.json")
                                if os.path.exists(failover_path):
                                    with open(failover_path, "r") as f:
                                        fdata = json.load(f)
                                    
                                    new_target = "secondary" if fdata.get("current") == "primary" else "primary"
                                    ep = fdata.get(new_target)
                                    if ep:
                                        fdata["current"] = new_target
                                        with open(failover_path, "w") as f:
                                            json.dump(fdata, f)
                                            
                                        config_path = os.path.join(WG_CONFIG_DIR, f"{WG_INTERFACE}.conf")
                                        tunnel.write_config(fdata["priv"], fdata["assigned_ip"], fdata["server_pubkey"], ep, config_path)
                                        tunnel.disconnect(WG_INTERFACE)
                                        tunnel.connect(WG_INTERFACE, assigned_ip)
    
                            if tun_status == "connected":
                                import ipaddress
                                lan_subnet = None
                                if lan_ip:
                                    try:
                                        lan_subnet = str(ipaddress.ip_network(f"{lan_ip}/24", strict=False))
                                    except Exception:
                                        pass
                                
                                api.send_heartbeat(
                                    node_id=node_id,
                                    network_id=network_id,
                                    zt_ip=tun_ip,
                                    lan_ip=lan_ip,
                                    hostname=socket.gethostname(),
                                    lan_subnet=lan_subnet
                                )
                            
                        except Exception:
                            pass
                        time.sleep(5)
                threading.Thread(target=_do_heartbeat, daemon=True).start()

        role = self._user_info.get("role", "")
        if role == "system_owner":
            self._main = OwnerWindow(api, self._user_info)
        else:
            self._main = MainWindow(api, self._user_info)
        self._main.logged_out.connect(self._on_logout)
        self.root.set_view(self._main)

    def _on_logout(self):
        self._user_info = {}
        self._token_data = {}
        api.logout()
        # pyrefly: ignore [missing-import]
        from services.websocket_client import ws_client
        ws_client.disconnect_ws()
        self._show_login()

    def run(self) -> int:
        self.root.showMaximized()
        # pyrefly: ignore [missing-import]
        from widgets.common import cleanup_workers
        # pyrefly: ignore [missing-import]
        from services.websocket_client import ws_client
        
        def _on_quit():
            cleanup_workers()
            ws_client.disconnect_ws()
            
        self.qt_app.aboutToQuit.connect(_on_quit)
        return self.qt_app.exec()


if __name__ == "__main__":
    sys.exit(App().run())
