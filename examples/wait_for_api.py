#!/usr/bin/env python3
"""Poll until API is ready; run before examples that call the API."""
import os
import sys
import time

# Windows: force UTF-8 for stdout/stderr
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

try:
    import requests
except ImportError:
    print("Install: pip install requests", file=sys.stderr, flush=True)
    sys.exit(1)

BASE = os.environ.get("TRUSTED_COMPUTE_API", "http://localhost:8000")
MAX_WAIT = int(os.environ.get("TRUSTED_COMPUTE_WAIT_SEC", "60"))
INTERVAL = 2


def main():
    url = f"{BASE.rstrip('/')}/"
    print(f"等待 API 就绪: {url} (最多 {MAX_WAIT}s)", flush=True)
    for i in range(0, MAX_WAIT, INTERVAL):
        try:
            r = requests.get(url, timeout=5)
            if r.status_code == 200:
                print("API 已就绪", flush=True)
                return
        except Exception as e:
            print(f"  [{i}s] 未就绪: {e}", flush=True)
        time.sleep(INTERVAL)
    print("超时，API 未就绪", file=sys.stderr, flush=True)
    sys.exit(1)


if __name__ == "__main__":
    main()
