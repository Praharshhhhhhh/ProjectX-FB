# pyrefly: ignore [missing-import]
from database import engine
from sqlalchemy import text

def migrate():
    try:
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE tenants ADD COLUMN network_owner_id INTEGER;"))
            conn.execute(text("ALTER TABLE tenants ADD CONSTRAINT fk_tenant_network_owner FOREIGN KEY(network_owner_id) REFERENCES users(id);"))
            conn.commit()
            print("Added network_owner_id to tenants")
    except Exception as e:
        print(f"Skipping tenants alter: {e}")
        
    try:
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE devices ADD COLUMN owner_id INTEGER;"))
            conn.execute(text("ALTER TABLE devices ADD CONSTRAINT fk_device_owner FOREIGN KEY(owner_id) REFERENCES users(id);"))
            conn.commit()
            print("Added owner_id to devices")
    except Exception as e:
        print(f"Skipping devices alter: {e}")
        
    try:
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE tenants ADD COLUMN max_second_masters INTEGER DEFAULT 2;"))
            conn.commit()
            print("Added max_second_masters to tenants")
    except Exception as e:
        print(f"Skipping max_second_masters alter: {e}")
        
    print("Migration complete!")

    try:
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE devices ADD COLUMN wg_public_key VARCHAR UNIQUE;"))
            conn.commit()
            print("Added wg_public_key to devices")
    except Exception as e:
        print(f"Skipping wg_public_key alter: {e}")
        
    try:
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE devices ADD COLUMN wg_ip VARCHAR;"))
            conn.commit()
            print("Added wg_ip to devices")
    except Exception as e:
        print(f"Skipping wg_ip alter: {e}")

    try:
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE devices ADD COLUMN tunnel_type VARCHAR DEFAULT 'zerotier';"))
            conn.commit()
            print("Added tunnel_type to devices")
    except Exception as e:
        print(f"Skipping tunnel_type alter: {e}")

    try:
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE tenants ADD COLUMN wg_server_public_key VARCHAR;"))
            conn.commit()
            print("Added wg_server_public_key to tenants")
    except Exception as e:
        print(f"Skipping wg_server_public_key alter: {e}")

    try:
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE tenants ADD COLUMN wg_server_endpoint VARCHAR;"))
            conn.commit()
            print("Added wg_server_endpoint to tenants")
    except Exception as e:
        print(f"Skipping wg_server_endpoint alter: {e}")

    try:
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE tenants ADD COLUMN wg_server_interface VARCHAR DEFAULT 'wg0';"))
            conn.commit()
            print("Added wg_server_interface to tenants")
    except Exception as e:
        print(f"Skipping wg_server_interface alter: {e}")

if __name__ == "__main__":
    migrate()
