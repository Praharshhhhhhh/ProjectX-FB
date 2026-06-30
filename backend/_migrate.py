import psycopg2

conn = psycopg2.connect(
    dbname="ProjectX-WG",
    user="postgres",
    password="Praharsh@0103",
    host="localhost",
    port=5432,
)
cur = conn.cursor()

# Check existing columns
cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name='users' ORDER BY ordinal_position")
cols = [r[0] for r in cur.fetchall()]
print("Current columns:", cols)

if "first_login_otp_done" not in cols:
    print("Adding first_login_otp_done column...")
    cur.execute("ALTER TABLE users ADD COLUMN first_login_otp_done BOOLEAN DEFAULT FALSE")
    conn.commit()
    print("Done!")
else:
    print("Column already exists.")

conn.close()
