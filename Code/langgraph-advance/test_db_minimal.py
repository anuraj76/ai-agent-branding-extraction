"""Minimal Databricks test - print at every step."""

import os
import sys
import ssl

# Load .env
print("[INIT] Loading .env...", flush=True)
with open('.env', 'r') as f:
    for line in f:
        if line.strip() and not line.startswith('#'):
            key, val = line.strip().split('=', 1)
            os.environ[key] = val
print("[INIT] .env loaded", flush=True)

# Disable SSL
print("[INIT] Patching SSL...", flush=True)
_orig = ssl.create_default_context
def _patch(*args, **kwargs):
    ctx = _orig(*args, **kwargs)
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx
ssl.create_default_context = _patch
print("[INIT] SSL patched", flush=True)

print("[INIT] Importing databricks.sql...", flush=True)
from databricks import sql
print("[INIT] Import complete", flush=True)

print("\n[TEST] Starting connection...", flush=True)
try:
    host = os.getenv("DATABRICKS_HOST")
    path = os.getenv("DATABRICKS_HTTP_PATH")
    token = os.getenv("DATABRICKS_TOKEN")

    print(f"[TEST] Connecting to: {host}", flush=True)
    conn = sql.connect(
        server_hostname=host,
        http_path=path,
        personal_access_token=token,
    )
    print("[TEST] ✓ Connected!", flush=True)

    print("[TEST] Creating cursor...", flush=True)
    cursor = conn.cursor()
    print("[TEST] ✓ Cursor created!", flush=True)

    print("[TEST] Executing query...", flush=True)
    cursor.execute("SELECT 1 as test")
    print("[TEST] ✓ Execute returned!", flush=True)

    print("[TEST] Fetching results...", flush=True)
    result = cursor.fetchall()
    print(f"[TEST] ✓ Fetched: {result}", flush=True)

    print("[TEST] Closing...", flush=True)
    cursor.close()
    conn.close()
    print("[TEST] ✓ SUCCESS!", flush=True)

except Exception as e:
    print(f"[ERROR] {type(e).__name__}: {e}", flush=True)
    import traceback
    traceback.print_exc()
    sys.exit(1)
