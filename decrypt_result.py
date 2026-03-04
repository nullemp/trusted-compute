import os
import sys
import argparse

# 确保项目根在 sys.path 里
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# 直接用 sandbox.runner 里的解密实现
from backend.sandbox.runner import _sm4_cbc_decrypt_py as sm4_cbc_decrypt_py  # type: ignore


def decrypt_result_bin(result_path: str, key_hex: str, save_as: str | None = None) -> None:
    key = bytes.fromhex(key_hex.strip())

    with open(result_path, "rb") as f:
        raw = f.read()

    if len(raw) <= 16:
        raise ValueError("结果文件长度太短，缺少 IV 或密文")

    iv = raw[:16]
    cipher = raw[16:]

    plaintext = sm4_cbc_decrypt_py(key, iv, cipher)
    text = plaintext.decode("utf-8", errors="ignore")

    if save_as:
        out_path = os.path.abspath(save_as)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"解密完成，已保存到: {out_path}")
    else:
        print(text)


def main() -> None:
    parser = argparse.ArgumentParser(description="解密 [IV+SM4-CBC密文] 文件为明文 SQL/JSON")
    parser.add_argument("result_path", help="要解密的 .bin 文件路径（data.bin 或 result_xxx.bin）")
    parser.add_argument(
        "--key-hex",
        default="00112233445566778899AABBCCDDEEFF",
        help="16 字节密钥的 hex（32 个十六进制字符），默认与示例一致",
    )
    parser.add_argument(
        "--out",
        dest="save_as",
        default=None,
        help="可选：将明文保存到指定文件路径，不填则直接打印到控制台",
    )
    args = parser.parse_args()
    decrypt_result_bin(args.result_path, args.key_hex, args.save_as)


if __name__ == "__main__":
    main()