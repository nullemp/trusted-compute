#!/usr/bin/env python3
"""
SQL 接口测试：仅测试 POST /api/execute-sql（沙箱 SQLite）。
用法（先启动服务）:
  python examples/test_sql.py
  TRUSTED_COMPUTE_API=http://localhost:8000 python examples/test_sql.py
Windows 也可用 PowerShell: .\examples\test_sql.ps1
"""
import os
import sys

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

def out(*args, **kwargs):
    kwargs.setdefault("flush", True)
    print(*args, **kwargs)

try:
    import requests
except ImportError:
    out("请安装: pip install requests", file=sys.stderr)
    sys.exit(1)

BASE = os.environ.get("TRUSTED_COMPUTE_API", "http://localhost:8000").rstrip("/")

FAILED = 0
PASSED = 0


def ok(name: str):
    global PASSED
    PASSED += 1
    out(f"  [OK] {name}")


def fail(name: str, msg: str):
    global FAILED
    FAILED += 1
    out(f"  [FAIL] {name}: {msg}")


def test_execute_sql():
    """POST /api/execute-sql：单表 + SQL"""
    name = "POST /api/execute-sql"
    try:
        r = requests.post(
            f"{BASE}/api/execute-sql",
            json={
                "data": [
                    {"id": 1, "name": "A", "v": 10},
                    {"id": 2, "name": "B", "v": 20},
                ],
                "sql": "SELECT name, v FROM input_data WHERE v >= 15",
                "table_name": "input_data",
            },
            timeout=60,
        )
        r.raise_for_status()
        resp = r.json()
        if resp.get("status") != "success":
            fail(name, resp.get("error", "status != success"))
            return
        result = resp.get("result") or {}
        if "columns" in result and "data" in result:
            if result["columns"] == ["name", "v"] and result["data"] == [["B", 20]]:
                ok(name)
            else:
                fail(name, f"unexpected result: {result}")
        else:
            fail(name, "missing result.columns or result.data")
    except Exception as e:
        fail(name, str(e))


def main():
    out("API:", BASE)
    try:
        r = requests.get(f"{BASE}/", timeout=5)
        r.raise_for_status()
    except Exception as e:
        out("服务未就绪，请先启动（Windows: scripts\\start-for-client.ps1）:", e, file=sys.stderr)
        sys.exit(2)

    out("\n--- SQL 接口测试 ---\n")
    test_execute_sql()

    out(f"\n通过: {PASSED}, 失败: {FAILED}")
    if FAILED:
        out("结果: 失败", file=sys.stderr)
        sys.exit(1)
    out("结果: 成功")
    sys.exit(0)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        out("脚本异常:", e, file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
