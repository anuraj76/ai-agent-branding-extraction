"""Test Databricks with environment variable auth."""

import os
import ssl

# Load .env
with open('.env', 'r') as f:
    for line in f:
        if line.strip() and not line.startswith('#'):
            key, val = line.strip().split('=', 1)
            os.environ[key] = val

# Set environment variables for databricks-sql-connector
os.environ['DATABRICKS_SERVER_HOSTNAME'] = os.getenv("DATABRICKS_HOST")
os.environ['DATABRICKS_HTTP_PATH'] = os.getenv("DATABRICKS_HTTP_PATH")
os.environ['DATABRICKS_TOKEN'] = os.getenv("DATABRICKS_TOKEN")

# Disable SSL
_orig = ssl.create_default_context
def _patch(*args, **kwargs):
    ctx = _orig(*args, **kwargs)
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx
ssl.create_default_context = _patch

from databricks import sql

print("[TEST] Connecting with env vars...", flush=True)
try:
    # Connect without parameters - should read from env
    conn = sql.connect()
    print("[TEST] ✓ Connected!", flush=True)

    cursor = conn.cursor()
    print("[TEST] Executing: SELECT 1", flush=True)
    cursor.execute("SELECT 1 as test")
    result = cursor.fetchall()
    print(f"[TEST] ✓ Result: {result}", flush=True)

    cursor.close()
    conn.close()
    print("[SUCCESS] Databricks works!", flush=True)

except Exception as e:
    print(f"[ERROR] {type(e).__name__}: {e}", flush=True)
