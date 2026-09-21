import os
import sys
import time
import json
import urllib.request
import urllib.error
import subprocess

CONFIG_PATH = "/etc/setulink/config.json"
API_BASE = "http://api.setulink.io/api"

def load_config():
    if not os.path.exists(CONFIG_PATH):
        local_path = "config.json"
        if os.path.exists(local_path):
            with open(local_path, "r") as f:
                return json.load(f)
        else:
            print("No config file found. Agent cannot start.")
            sys.exit(1)
    with open(CONFIG_PATH, "r") as f:
        return json.load(f)

def get_zt_node_id():
    try:
        zt_cmd = ["zerotier-cli"] if os.name != 'nt' else [r"C:\ProgramData\ZeroTier\One\zerotier-one_x64.exe", "-q"]
        proc = subprocess.run(zt_cmd + ["info"], capture_output=True, text=True, check=True)
        # Expected output: "200 info <node_id> <version> ONLINE"
        parts = proc.stdout.split()
        if len(parts) >= 3 and parts[1] == "info":
            return parts[2]
        raise Exception("Unexpected output format")
    except Exception as e:
        print(f"Failed to get ZeroTier node ID. Is zerotier-one running? {e}")
        sys.exit(1)

def join_zt_network(network_id):
    try:
        print(f"Joining ZeroTier network {network_id}...")
        if os.name == 'nt':
            # On Windows, the CLI tool often fails with "401 join {}". 
            # We bypass it by hitting the local ZeroTier service API directly.
            token_path = r"C:\ProgramData\ZeroTier\One\authtoken.secret"
            with open(token_path, "r") as f:
                token = f.read().strip()
            
            req = urllib.request.Request(
                f"http://localhost:9993/network/{network_id}",
                data=json.dumps({}).encode('utf-8'),
                headers={"X-ZT1-Auth": token, "Content-Type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=5) as response:
                if response.status == 200:
                    print("Successfully joined ZeroTier network via Local API.")
                else:
                    print(f"Failed to join via Local API: {response.status}")
        else:
            zt_cmd = ["zerotier-cli"]
            subprocess.run(zt_cmd + ["join", network_id], check=True, capture_output=True)
            print("Successfully joined ZeroTier network.")
    except Exception as e:
        print(f"Failed to join ZeroTier network automatically: {e}")
        print(f"Please ensure you join the network {network_id} manually (e.g., via the ZeroTier UI).")

def is_admin():
    try:
        import ctypes
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

def run():
    config = load_config()
    serial_number = config.get("serial_number")
    activation_key = config.get("activation_key")
    api_url = config.get("api_url", API_BASE)
    
    if not serial_number:
        print("Missing serial_number in config.")
        sys.exit(1)

    lan_subnet = config.get("lan_subnet")

    zt_node_id = config.get("zerotier_node_id")
    if not zt_node_id:
        zt_node_id = get_zt_node_id()
        print(f"ZeroTier Node ID (from CLI): {zt_node_id}")
    else:
        print(f"ZeroTier Node ID (from config): {zt_node_id}")

    payload = {
        "serial_number": serial_number,
        "activation_key": activation_key,
        "zerotier_node_id": zt_node_id
    }
    if lan_subnet:
        payload["lan_subnet"] = lan_subnet

    
    req = urllib.request.Request(
        f"{api_url}/routers/provision",
        data=json.dumps(payload).encode('utf-8'),
        headers={"Content-Type": "application/json"}
    )
    
    print("Requesting provisioning from backend...")
    while True:
        try:
            with urllib.request.urlopen(req, timeout=10) as response:
                data = json.loads(response.read().decode())
                
                if data.get("status") == "pending":
                    print(f"Provisioning in progress: {data.get('message', 'Waiting for authorization')}. Retrying in 5s...")
                    time.sleep(5)
                    continue
                    
                if data.get("status") == "ok":
                    print("Provisioning successful!")
                    zt_network_id = data.get("zt_network_id")
                    
                    if zt_network_id:
                        if os.name == 'nt':
                            print(f"Skipping automatic network join on Windows. Please ensure you are connected to {zt_network_id} in the ZeroTier UI.")
                        else:
                            join_zt_network(zt_network_id)
                    else:
                        print("Warning: Backend did not return a ZT network ID.")
                    
                    # Daemon loop: send heartbeats
                    while True:
                        time.sleep(60)
                        try:
                            hb_req = urllib.request.Request(
                                f"{api_url}/routers/heartbeat",
                                data=json.dumps({"serial_number": serial_number}).encode('utf-8'),
                                headers={"Content-Type": "application/json"}
                            )
                            urllib.request.urlopen(hb_req, timeout=10)
                            print("Heartbeat sent.")
                        except Exception as e:
                            print(f"Heartbeat failed: {e}")
                            
        except urllib.error.URLError as e:
            print(f"Failed to connect to backend: {e}. Retrying in 15 seconds...")
            time.sleep(15)
        except urllib.error.HTTPError as e:
            print(f"Provisioning rejected by backend: {e.code} {e.reason}")
            sys.exit(1)
        except Exception as e:
            print(f"Unexpected error: {e}")
            time.sleep(15)

if __name__ == "__main__":
    run()
