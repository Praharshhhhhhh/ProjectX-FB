import sys
import os
sys.path.insert(0, os.path.abspath("backend"))

from database import SessionLocal
from models import Device

db = SessionLocal()
devices = db.query(Device).all()
print("Total devices:", len(devices))
for d in devices:
    print(f"Device: {d.id} | Name: {d.name} | WG_IP: {d.wg_ip} | Status: {d.status}")
