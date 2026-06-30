import psycopg2

conn = psycopg2.connect(
    dbname="ProjectX-WG",
    user="postgres",
    password="Praharsh@0103",
    host="localhost",
    port=5432,
)
cur = conn.cursor()

try:
    print("Fixing routers constraint...")
    # Drop existing constraint
    cur.execute("ALTER TABLE routers DROP CONSTRAINT IF EXISTS routers_claimed_by_user_id_fkey")
    # Add new constraint with ON DELETE SET NULL
    cur.execute("ALTER TABLE routers ADD CONSTRAINT routers_claimed_by_user_id_fkey FOREIGN KEY (claimed_by_user_id) REFERENCES users(id) ON DELETE SET NULL")
    
    print("Fixing activation_keys constraint...")
    cur.execute("ALTER TABLE activation_keys DROP CONSTRAINT IF EXISTS activation_keys_used_by_user_id_fkey")
    cur.execute("ALTER TABLE activation_keys ADD CONSTRAINT activation_keys_used_by_user_id_fkey FOREIGN KEY (used_by_user_id) REFERENCES users(id) ON DELETE SET NULL")
    
    conn.commit()
    print("Constraints updated successfully.")
except Exception as e:
    conn.rollback()
    print(f"Error: {e}")
finally:
    conn.close()
