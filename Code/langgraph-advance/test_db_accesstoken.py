"""Test Databricks with access_token parameter."""

import os
import ssl

# Load .env
with open('.env', 'r') as f:
    for line in f:
        if line.strip() and not line.startswith('#'):
            key, val = line.strip().split('=', 1)
            os.environ[key] = val

# Disable SSL
_orig = ssl.create_default_context
def _patch(*args, **kwargs):
    ctx = _orig(*args, **kwargs)
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx
ssl.create_default_context = _patch

from databricks import sql

print("[TEST] Method 1: access_token parameter...", flush=True)
try:
    conn = sql.connect(
        server_hostname=os.getenv("DATABRICKS_HOST"),
        http_path=os.getenv("DATABRICKS_HTTP_PATH"),
        access_token=os.getenv("DATABRICKS_TOKEN"),
    )
    print("[SUCCESS] Connected with access_token!", flush=True)
    conn.close()
except Exception as e:
    print(f"[FAILED] {type(e).__name__}", flush=True)

print("\n[TEST] Method 2: access_token + username='token'...", flush=True)
try:
    conn = sql.connect(
        server_hostname=os.getenv("DATABRICKS_HOST"),
        http_path=os.getenv("DATABRICKS_HTTP_PATH"),
        username="token",
        password=os.getenv("DATABRICKS_TOKEN"),
    )
    print("[SUCCESS] Connected with username/password!", flush=True)
    conn.close()
except Exception as e:
    print(f"[FAILED] {type(e).__name__}", flush=True)
