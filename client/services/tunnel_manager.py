import services.wireguard_local as wg
import services.zerotier_local as zt
import os
from config import WG_CONFIG_DIR

class TunnelManager:
    def __init__(self, device: dict):
        self.device = device
        conn_info = device.get("connection_info", {})
        self.tunnel_type = conn_info.get("tunnel_type", "zerotier")
        self.network_id = conn_info.get("network_id")
        self.device_id = device.get("id")
        
    @classmethod
    def is_local_device(cls, device: dict) -> bool:
        tunnel_type = device.get("connection_info", {}).get("tunnel_type", "zerotier")
        if tunnel_type == "wireguard":
            existing_priv, existing_pub = wg.get_or_create_keypair()
            return device.get("wg_public_key") == existing_pub
        else:
            if not zt.is_running(): return False
            node_id = zt.get_node_info().get("address")
            return device.get("zerotier_node_id") == node_id

    def connect(self, api_client, conf_data: str = None) -> bool:
        if self.tunnel_type == "wireguard":
            if not conf_data:
                conf_data = api_client.download_conf(self.device_id)
            if not conf_data:
                return False
                
            if "REPLACE_ME" in conf_data:
                existing_priv, _ = wg.get_or_create_keypair()
                conf_data = conf_data.replace("REPLACE_ME", existing_priv)
                
            config_path = os.path.join(WG_CONFIG_DIR, f"projectx_{self.device_id}.conf")
            # Write config file
            try:
                os.makedirs(WG_CONFIG_DIR, exist_ok=True)
                with open(config_path, "w") as f:
                    f.write(conf_data)
            except Exception:
                return False
                
            return wg.connect(config_path)
        else:
            if not self.network_id:
                return False
            return zt.connect(self.network_id)

    def disconnect(self) -> bool:
        if self.tunnel_type == "wireguard":
            config_path = os.path.join(WG_CONFIG_DIR, f"projectx_{self.device_id}.conf")
            return wg.disconnect(config_path)
        else:
            if not self.network_id:
                return False
            return zt.disconnect(self.network_id)

    def get_status(self) -> str:
        if self.tunnel_type == "wireguard":
            config_path = os.path.join(WG_CONFIG_DIR, f"projectx_{self.device_id}.conf")
            return wg.get_status(config_path)
        else:
            if not self.network_id:
                return "disconnected"
            return zt.get_status(self.network_id)
