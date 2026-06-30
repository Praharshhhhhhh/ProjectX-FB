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
    print("Adding master_activation_key to tenants...")
    cur.execute("ALTER TABLE tenants ADD COLUMN IF NOT EXISTS master_activation_key VARCHAR(255)")
    conn.commit()
    print("Column added successfully.")
except Exception as e:
    conn.rollback()
    print(f"Error: {e}")
finally:
    conn.close()
