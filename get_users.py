import sys
import os
sys.path.insert(0, os.path.abspath("backend"))

from database import SessionLocal
from models import User

db = SessionLocal()
users = db.query(User).all()
for u in users:
    print(u.email, u.hashed_password, u.totp_enabled)
