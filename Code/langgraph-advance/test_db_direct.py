"""Direct Databricks connection test with detailed logging."""

import os
import sys
import ssl
import time

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

print("=" * 80)
print("DATABRICKS CONNECTION TEST WITH DETAILED LOGGING")
print("=" * 80)

host = os.getenv("DATABRICKS_HOST")
path = os.getenv("DATABRICKS_HTTP_PATH")
token = os.getenv("DATABRICKS_TOKEN")

print(f"\nConfig:")
print(f"  Host: {host}")
print(f"  Path: {path}")
print(f"  Token: {token[:20]}...\n")

try:
    # Step 1: Connection
    print("[1/5] Creating connection object...")
    start = time.time()
    conn = sql.connect(
        server_hostname=host,
        http_path=path,
        personal_access_token=token,
    )
    elapsed = time.time() - start
    print(f"      ✓ Connected in {elapsed:.2f}s\n")

    # Step 2: Create cursor
    print("[2/5] Creating cursor...")
    start = time.time()
    cursor = conn.cursor()
    elapsed = time.time() - start
    print(f"      ✓ Cursor created in {elapsed:.2f}s\n")

    # Step 3: Execute simple query
    print("[3/5] Executing: SELECT 1 as test")
    start = time.time()
    cursor.execute("SELECT 1 as test")
    elapsed = time.time() - start
    print(f"      ✓ Execute() completed in {elapsed:.2f}s\n")

    # Step 4: Fetch results
    print("[4/5] Fetching results...")
    start = time.time()
    result = cursor.fetchall()
    elapsed = time.time() - start
    print(f"      ✓ Fetched in {elapsed:.2f}s")
    print(f"      Result: {result}\n")

    # Step 5: Cleanup
    print("[5/5] Closing cursor and connection...")
    cursor.close()
    conn.close()
    print("      ✓ Closed\n")

    print("=" * 80)
    print("✓ SUCCESS - Direct Databricks query works!")
    print("=" * 80)

except Exception as e:
    print(f"\n✗ ERROR: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
