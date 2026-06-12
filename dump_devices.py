import os
import sys

# Add backend directory to sys.path so imports work
backend_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "backend")
sys.path.insert(0, backend_dir)

# Set working directory to backend so dotenv loads properly
os.chdir(backend_dir)

# pyrefly: ignore [missing-import]
from database import SessionLocal
# pyrefly: ignore [missing-import]
from models import Device

db = SessionLocal()
devices = db.query(Device).all()
for d in devices:
    print(f"ID: {d.id}")
    print(f"Name: {d.name}")
    print(f"Status: {d.status}")
    print(f"ZT Node: {d.zerotier_node_id}")
    print(f"ZT IP: {d.zerotier_ip}")
    print(f"LAN IP: {d.lan_ip}")
    print("-" * 20)
