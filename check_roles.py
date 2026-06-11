import os
import psycopg2
from dotenv import load_dotenv

# Load .env FIRST, before reading any env vars — your established pattern
# (gunicorn imports the module directly, so this has to run at import time)
load_dotenv()

# Use the SAME variable your app connects with, so this reflects reality
conn_str = os.getenv("DATABASE_URL")   # rename if yours is different

conn = psycopg2.connect(conn_str)
cur = conn.cursor()

# current_user  -> the role your queries actually execute as
# rolsuper      -> superuser? (superusers always bypass RLS)
# rolbypassrls  -> has the BYPASSRLS attribute? (also bypasses RLS)
cur.execute("""
    SELECT current_user, rolsuper, rolbypassrls
    FROM pg_roles
    WHERE rolname = current_user;
""")

role, is_super, bypass_rls = cur.fetchone()
print(f"Role:         {role}")
print(f"Superuser:    {is_super}")
print(f"Bypasses RLS: {bypass_rls}")

cur.close()
conn.close()