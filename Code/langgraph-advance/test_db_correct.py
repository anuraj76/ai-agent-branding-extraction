"""Test with correct access_token parameter."""

import os
import ssl

with open('.env', 'r') as f:
    for line in f:
        if line.strip() and not line.startswith('#'):
            k, v = line.strip().split('=', 1)
            os.environ[k] = v

_orig = ssl.create_default_context
def _p(*a, **kw):
    c = _orig(*a, **kw)
    c.check_hostname = False
    c.verify_mode = ssl.CERT_NONE
    return c
ssl.create_default_context = _p

from databricks import sql

print("Connecting...", flush=True)
try:
    conn = sql.connect(
        server_hostname=os.getenv("DATABRICKS_HOST"),
        http_path=os.getenv("DATABRICKS_HTTP_PATH"),
        access_token=os.getenv("DATABRICKS_TOKEN"),
    )
    print("✓ Connected!", flush=True)

    cursor = conn.cursor()
    cursor.execute("SELECT 1 as test")
    result = cursor.fetchall()
    print(f"✓ Result: {result}", flush=True)

    cursor.close()
    conn.close()
    print("✓ SUCCESS!", flush=True)

except Exception as e:
    print(f"✗ {type(e).__name__}: {e}", flush=True)
