# pyrefly: ignore [missing-import]
from database import engine, SessionLocal
# pyrefly: ignore [missing-import]
from models import Tenant, User, UserRole

def backfill():
    db = SessionLocal()
    try:
        tenants = db.query(Tenant).filter(Tenant.zerotier_network_id != None).all()
        count = 0
        for t in tenants:
            if not t.network_owner_id:
                master = db.query(User).filter(User.tenant_id == t.id, User.role == UserRole.master).first()
                if master:
                    t.network_owner_id = master.id
                    count += 1
                    print(f"Backfilled tenant {t.company_name} with master user {master.email}")
        
        db.commit()
        print(f"Backfilled {count} tenants.")
    finally:
        db.close()

if __name__ == "__main__":
    backfill()
