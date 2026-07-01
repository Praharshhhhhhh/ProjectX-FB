import os
import sys
import time
import json
import urllib.request
import urllib.error
import subprocess

def _get_zt_cmd():
    if os.name == "nt":
        return ["C:\\ProgramData\\ZeroTier\\One\\zerotier-one_x64.exe", "-q"]
    return ["zerotier-cli"]

def get_zt_node_id():
    try:
        cmd = _get_zt_cmd() + ["info"]
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        parts = res.stdout.strip().split()
        if len(parts) >= 3 and parts[1] == "info":
            return parts[2]
    except Exception as e:
        print(f"Warning: Failed to get real ZeroTier Node ID ({e}). Using mock.")
    return "18881e4fa3"

def join_zt_network(network_id):
    try:
        print(f"Joining ZeroTier network {network_id}...")
        cmd = _get_zt_cmd() + ["join", network_id]
        subprocess.run(cmd, check=True)
    except Exception as e:
        print(f"Warning: Failed to join ZeroTier network ({e}).")

CONFIG_PATH = "config.json"
API_BASE = "http://api.setulink.io/api"

def load_config():
    if not os.path.exists(CONFIG_PATH):
        print(f"No {CONFIG_PATH} file found.")
        print("Please create one with:")
        print('{"serial_number": "RTR-...", "activation_key": "...", "api_url": "http://127.0.0.1:8001/api"}')
        sys.exit(1)
    with open(CONFIG_PATH, "r") as f:
        return json.load(f)

def run():
    config = load_config()
    serial_number = config.get("serial_number")
    activation_key = config.get("activation_key")
    api_url = config.get("api_url", API_BASE)
    
    if not serial_number:
        print("Missing serial_number in config.")
        sys.exit(1)

    zt_node_id = get_zt_node_id()
    print(f"Using ZeroTier Node ID: {zt_node_id}")

    payload = {
        "serial_number": serial_number,
        "activation_key": activation_key,
        "zerotier_node_id": zt_node_id
    }
    
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
                    print("\n✅ Provisioning successful!")
                    print(f"   ZeroTier Network ID: {data.get('zt_network_id')}")
                    print("\n[ZeroTier] Attempting to join network...")
                    join_zt_network(data.get('zt_network_id'))
                    
                    print("\n[Mock] Starting heartbeat loop (CTRL+C to stop)...")
                    while True:
                        time.sleep(10)
                        try:
                            hb_req = urllib.request.Request(
                                f"{api_url}/routers/heartbeat",
                                data=json.dumps({"serial_number": serial_number}).encode('utf-8'),
                                headers={"Content-Type": "application/json"}
                            )
                            urllib.request.urlopen(hb_req, timeout=10)
                            print("   [Heartbeat] Sent.")
                        except Exception as e:
                            print(f"   [Heartbeat] Failed: {e}")
                            
        except urllib.error.URLError as e:
            print(f"Failed to connect to backend: {e}. Retrying in 15 seconds...")
            time.sleep(15)
        except urllib.error.HTTPError as e:
            print(f"Provisioning rejected by backend: {e.code} {e.reason}")
            
            # Print response body if available (helps debug 403s etc)
            try:
                body = e.read().decode()
                print(f"Response: {body}")
            except:
                pass
                
            sys.exit(1)
        except Exception as e:
            print(f"Unexpected error: {e}")
            time.sleep(15)

if __name__ == "__main__":
    run()
