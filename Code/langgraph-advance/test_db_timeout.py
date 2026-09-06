"""Test Databricks with explicit timeout."""

import os
import ssl
import socket

# Load .env
with open('.env', 'r') as f:
    for line in f:
        if line.strip() and not line.startswith('#'):
            key, val = line.strip().split('=', 1)
            os.environ[key] = val

# Set socket timeout globally (5 seconds)
socket.setdefaulttimeout(5)

# Disable SSL
_orig = ssl.create_default_context
def _patch(*args, **kwargs):
    ctx = _orig(*args, **kwargs)
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx
ssl.create_default_context = _patch

from databricks import sql

print("[TEST] Connecting with 5-second timeout...", flush=True)
try:
    conn = sql.connect(
        server_hostname=os.getenv("DATABRICKS_HOST"),
        http_path=os.getenv("DATABRICKS_HTTP_PATH"),
        personal_access_token=os.getenv("DATABRICKS_TOKEN"),
    )
    print("[TEST] ✓ Connected!", flush=True)
    conn.close()
except Exception as e:
    print(f"[ERROR] {type(e).__name__}: {e}", flush=True)
