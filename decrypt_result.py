#!/usr/bin/env python3
"""
解密 backend/results/.../result_*.bin 文件，并打印明文 JSON。

用法（PowerShell 示例）：
  python decrypt_result.py ^
    --file backend/results/da1478ef32c44a92/result_1772609557626.bin ^
    --key 00112233445566778899AABBCCDDEEFF
"""

import argparse
import json
import os
import sys

# 复用 sandbox/runner.py 里的 SM4 解密实现
sys.path.append(os.path.join(os.path.dirname(__file__), "backend"))
from sandbox.runner import _sm4_cbc_decrypt_py  # type: ignore[attr-defined]


def decrypt_file(path: str, key_hex: str) -> bytes:
    with open(path, "rb") as f:
        data = f.read()
    if len(data) < 16:
        raise ValueError("文件长度不足 16 字节，无法取 IV")
    iv = data[:16]
    cipher = data[16:]
    key = bytes.fromhex(key_hex.strip())
    return _sm4_cbc_decrypt_py(key=key, iv=iv, data=cipher)


def main() -> None:
    parser = argparse.ArgumentParser(description="解密 result_*.bin 并打印明文 JSON")
    parser.add_argument("--file", required=True, help="result_*.bin 文件路径")
    parser.add_argument(
        "--key",
        required=True,
        help="明文密钥（16 字节 hex，如 00112233445566778899AABBCCDDEEFF）",
    )
    args = parser.parse_args()

    plaintext = decrypt_file(args.file, args.key)
    try:
        obj = json.loads(plaintext.decode("utf-8"))
        print(json.dumps(obj, ensure_ascii=False, indent=2))
    except Exception:
        # 不是 JSON 就直接以文本/十六进制形式输出
        try:
            print(plaintext.decode("utf-8", errors="replace"))
        except Exception:
            print(plaintext.hex())


if __name__ == "__main__":
    main()