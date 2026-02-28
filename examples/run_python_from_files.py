#!/usr/bin/env python3
"""
加密数据文件上传示例（SM4-CBC + PKCS7）：

- 默认：
  data_file: 你本地准备好的「加密后的 enterprise_dump.json」二进制文件
  model_file: examples/models/enterprise_aggregate_model.py（仅负责计算）

- 通过命令行参数指定（Windows PowerShell 示例）：
  python examples/run_python_from_files.py ^
    --data path\\to\\encrypted_dump.bin ^
    --model examples\\models\\enterprise_aggregate_model.py ^
    --key 00112233445566778899AABBCCDDEEFF ^
    --iv  0102030405060708090A0B0C0D0E0F10

说明：
- data_file 始终视为「加密后的原始字节流」，不会在客户端解析 JSON；
- 必须提供明文密钥 (--key) 和 IV (--iv)，后端会将二进制 + key/iv 透传到 sandbox，
  由沙箱 runner 在沙箱内用 C 版 SM4-CBC 分块解密并解析 JSON，再把解密后的数据作为 input_params['data'] 交给 enterprise_aggregate_model.py。
"""

import os
import sys
import json
import argparse

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

try:
    import requests
except ImportError:
    print("请先安装依赖: pip install -r examples/requirements.txt", file=sys.stderr)
    sys.exit(1)

BASE = os.environ.get("TRUSTED_COMPUTE_API", "http://localhost:8000").rstrip("/")
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR, "data")
MODELS_DIR = os.path.join(SCRIPT_DIR, "models")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="将数据文件和 Python 模型脚本上传到 /api/python-from-files，在 sandbox 中执行计算。",
    )
    parser.add_argument(
        "--data",
        dest="data_path",
        required=True,
        help="加密后数据文件路径（二进制密文，格式为 [16 字节 IV] + [密文]，例如由 enterprise_dump.json 经 SM4-CBC+PKCS7 加密得到）",
    )
    parser.add_argument(
        "--model",
        dest="model_path",
        default=os.path.join(MODELS_DIR, "enterprise_aggregate_model.py"),
        help="Python 模型脚本路径，默认 examples/models/enterprise_aggregate_model.py（只做业务计算，不关心加解密）",
    )
    parser.add_argument(
        "--key",
        dest="key_hex",
        required=True,
        help="必填：对称加密明文密钥（16 字节 hex 编码，如 00112233445566778899AABBCCDDEEFF）",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    print("API 地址:", BASE)
    try:
        health = requests.get(f"{BASE}/", timeout=5)
        health.raise_for_status()
    except Exception as e:
        print("服务未就绪，请先启动（Windows: scripts\\start-for-client.ps1）:", e, file=sys.stderr)
        sys.exit(1)

    data_path = args.data_path
    model_path = args.model_path
    if not os.path.isfile(data_path):
        print(f"未找到加密数据文件: {data_path}", file=sys.stderr)
        sys.exit(1)
    if not os.path.isfile(model_path):
        print(f"未找到模型脚本: {model_path}", file=sys.stderr)
        sys.exit(1)

    url = f"{BASE}/api/python-from-files"
    print("\n========== /api/python-from-files 示例 ==========\n")
    with open(data_path, "rb") as f_data, open(model_path, "rb") as f_model:
        files = {
            "data_file": (os.path.basename(data_path), f_data, "application/octet-stream"),
            "model_file": (os.path.basename(model_path), f_model, "text/x-python"),
        }
        data = {
            "key_hex": args.key_hex,
        }
        r = requests.post(url, files=files, data=data, timeout=300)

    r.raise_for_status()
    out = r.json()
    if out.get("status") == "error":
        print("错误:", out.get("error"), file=sys.stderr)
        sys.exit(1)

    result = out.get("result", {})
    # runner 对 DataFrame 返回: {"type": "dataframe", "columns": [...], "data": [...], "shape": [...]}
    if result.get("type") == "dataframe":
        cols = result.get("columns") or []
        rows = result.get("data") or []
        print("结果列:", cols)
        print("总行数:", len(rows))
        print("前 10 行:")
        for row in rows[:10]:
            print(" ", row)
    else:
        print("结果:", json.dumps(result, ensure_ascii=False, indent=2))

    print("\n========== 结束 ==========\n")


if __name__ == "__main__":
    main()

