import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from config import BACKEND_URL
import requests

def test_register():
    node_id = "ecfbb790a7"
    network_id = "41d49af6c22069da"
    try:
        res = requests.post(f"{BACKEND_URL}/api/devices/register", json={
            "zerotier_node_id": node_id,
            "network_id": network_id,
            "hostname": "Test-PC"
        })
        print(res.status_code)
        print(res.text)
    except Exception as e:
        print("Error:", e)

if __name__ == "__main__":
    test_register()
