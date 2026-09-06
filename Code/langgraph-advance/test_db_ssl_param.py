"""Test Databricks with SSL verification disabled in connection params."""

import os
import ssl

# Load .env
with open('.env', 'r') as f:
    for line in f:
        if line.strip() and not line.startswith('#'):
            key, val = line.strip().split('=', 1)
            os.environ[key] = val

# Disable SSL globally
_orig = ssl.create_default_context
def _patch(*args, **kwargs):
    ctx = _orig(*args, **kwargs)
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx
ssl.create_default_context = _patch

from databricks import sql

print("[TEST] Testing with disable_ssl_verification...", flush=True)
try:
    conn = sql.connect(
        server_hostname=os.getenv("DATABRICKS_HOST"),
        http_path=os.getenv("DATABRICKS_HTTP_PATH"),
        access_token=os.getenv("DATABRICKS_TOKEN"),
        disable_ssl_verification=True,
    )
    print("[SUCCESS] Connected!", flush=True)

    cursor = conn.cursor()
    cursor.execute("SELECT 1 as test")
    result = cursor.fetchall()
    print(f"[SUCCESS] Result: {result}", flush=True)

    cursor.close()
    conn.close()
except Exception as e:
    print(f"[ERROR] {type(e).__name__}: {e}", flush=True)
