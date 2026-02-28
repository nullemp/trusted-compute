#!/usr/bin/env python3
"""
使用 SM4-CBC + PKCS7 将 examples/data/enterprise_dump.json 加密为二进制文件，
供 /api/python-from-files + run_python_from_files.py 测试使用。

加密后文件格式：
- 前 16 字节：IV
- 后续字节：SM4-CBC 密文（对整份 JSON 做 PKCS7 填充后加密）

用法示例（在项目根目录执行）：

  python examples/gen_enterprise_dump_encrypted_sm4_cbc.py

默认：
- 明文输入:  examples/data/enterprise_dump.json
- 密文输出: examples/data/enterprise_dump_encrypted.bin
- 若不指定 --key-hex，则随机生成 16 字节密钥，并打印 hex（供 run_python_from_files.py 使用）。

你也可以自己指定密钥（16 字节 -> 32 个十六进制字符）：

  python examples/gen_enterprise_dump_encrypted_sm4_cbc.py ^
    --key-hex 00112233445566778899AABBCCDDEEFF
"""

import argparse
import os
import sys
from typing import Tuple, List


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR, "data")

# 测试用写死的密钥和 IV（32 个十六进制字符 = 16 字节）
TEST_KEY_HEX = "00112233445566778899AABBCCDDEEFF"
TEST_IV_HEX = "0102030405060708090A0B0C0D0E0F10"


def _pkcs7_pad(data: bytes, block_size: int = 16) -> bytes:
    pad_len = block_size - (len(data) % block_size)
    if pad_len == 0:
        pad_len = block_size
    return data + bytes([pad_len]) * pad_len


# ==== 纯 Python SM4 实现（加密部分），与 runner.py 的解密逻辑兼容 ====

SBOX_TABLE: List[List[int]] = [
    [0xD6, 0x90, 0xE9, 0xFE, 0xCC, 0xE1, 0x3D, 0xB7, 0x16, 0xB6, 0x14, 0xC2, 0x28, 0xFB, 0x2C, 0x05],
    [0x2B, 0x67, 0x9A, 0x76, 0x2A, 0xBE, 0x04, 0xC3, 0xAA, 0x44, 0x13, 0x26, 0x49, 0x86, 0x06, 0x99],
    [0x9C, 0x42, 0x50, 0xF4, 0x91, 0xEF, 0x98, 0x7A, 0x33, 0x54, 0x0B, 0x43, 0xED, 0xCF, 0xAC, 0x62],
    [0xE4, 0xB3, 0x1C, 0xA9, 0xC9, 0x08, 0xE8, 0x95, 0x80, 0xDF, 0x94, 0xFA, 0x75, 0x8F, 0x3F, 0xA6],
    [0x47, 0x07, 0xA7, 0xFC, 0xF3, 0x73, 0x17, 0xBA, 0x83, 0x59, 0x3C, 0x19, 0xE6, 0x85, 0x4F, 0xA8],
    [0x68, 0x6B, 0x81, 0xB2, 0x71, 0x64, 0xDA, 0x8B, 0xF8, 0xEB, 0x0F, 0x4B, 0x70, 0x56, 0x9D, 0x35],
    [0x1E, 0x24, 0x0E, 0x5E, 0x63, 0x58, 0xD1, 0xA2, 0x25, 0x22, 0x7C, 0x3B, 0x01, 0x21, 0x78, 0x87],
    [0xD4, 0x00, 0x46, 0x57, 0x9F, 0xD3, 0x27, 0x52, 0x4C, 0x36, 0x02, 0xE7, 0xA0, 0xC4, 0xC8, 0x9E],
    [0xEA, 0xBF, 0x8A, 0xD2, 0x40, 0xC7, 0x38, 0xB5, 0xA3, 0xF7, 0xF2, 0xCE, 0xF9, 0x61, 0x15, 0xA1],
    [0xE0, 0xAE, 0x5D, 0xA4, 0x9B, 0x34, 0x1A, 0x55, 0xAD, 0x93, 0x32, 0x30, 0xF5, 0x8C, 0xB1, 0xE3],
    [0x1D, 0xF6, 0xE2, 0x2E, 0x82, 0x66, 0xCA, 0x60, 0xC0, 0x29, 0x23, 0xAB, 0x0D, 0x53, 0x4E, 0x6F],
    [0xD5, 0xDB, 0x37, 0x45, 0xDE, 0xFD, 0x8E, 0x2F, 0x03, 0xFF, 0x6A, 0x72, 0x6D, 0x6C, 0x5B, 0x51],
    [0x8D, 0x1B, 0xAF, 0x92, 0xBB, 0xDD, 0xBC, 0x7F, 0x11, 0xD9, 0x5C, 0x41, 0x1F, 0x10, 0x5A, 0xD8],
    [0x0A, 0xC1, 0x31, 0x88, 0xA5, 0xCD, 0x7B, 0xBD, 0x2D, 0x74, 0xD0, 0x12, 0xB8, 0xE5, 0xB4, 0xB0],
    [0x89, 0x69, 0x97, 0x4A, 0x0C, 0x96, 0x77, 0x7E, 0x65, 0xB9, 0xF1, 0x09, 0xC5, 0x6E, 0xC6, 0x84],
    [0x18, 0xF0, 0x7D, 0xEC, 0x3A, 0xDC, 0x4D, 0x20, 0x79, 0xEE, 0x5F, 0x3E, 0xD7, 0xCB, 0x39, 0x48],
]

FK = [0xA3B1BAC6, 0x56AA3350, 0x677D9197, 0xB27022DC]
CK = [
    0x00070E15, 0x1C232A31, 0x383F464D, 0x545B6269,
    0x70777E85, 0x8C939AA1, 0xA8AFB6BD, 0xC4CBD2D9,
    0xE0E7EEF5, 0xFC030A11, 0x181F262D, 0x343B4249,
    0x50575E65, 0x6C737A81, 0x888F969D, 0xA4ABB2B9,
    0xC0C7CED5, 0xDCE3EAF1, 0xF8FF060D, 0x141B2229,
    0x30373E45, 0x4C535A61, 0x686F767D, 0x848B9299,
    0xA0A7AEB5, 0xBCC3CAD1, 0xD8DFE6ED, 0xF4FB0209,
    0x10171E25, 0x2C333A41, 0x484F565D, 0x646B7279,
]


def _rotl(x: int, n: int) -> int:
    x &= 0xFFFFFFFF
    return ((x << n) & 0xFFFFFFFF) | (x >> (32 - n))


def _sbox(byte: int) -> int:
    return SBOX_TABLE[(byte >> 4) & 0x0F][byte & 0x0F]


def _tau(a: int) -> int:
    b0 = _sbox((a >> 24) & 0xFF)
    b1 = _sbox((a >> 16) & 0xFF)
    b2 = _sbox((a >> 8) & 0xFF)
    b3 = _sbox(a & 0xFF)
    return (b0 << 24) | (b1 << 16) | (b2 << 8) | b3


def _L(b: int) -> int:
    return b ^ _rotl(b, 2) ^ _rotl(b, 10) ^ _rotl(b, 18) ^ _rotl(b, 24)


def _L_key(b: int) -> int:
    return b ^ _rotl(b, 13) ^ _rotl(b, 23)


def _T(x: int) -> int:
    return _L(_tau(x))


def _T_key(x: int) -> int:
    return _L_key(_tau(x))


def sm4_key_schedule(key: bytes) -> list[int]:
    if len(key) != 16:
        raise ValueError("SM4 密钥长度必须为 16 字节")
    mk = [
        int.from_bytes(key[0:4], "big"),
        int.from_bytes(key[4:8], "big"),
        int.from_bytes(key[8:12], "big"),
        int.from_bytes(key[12:16], "big"),
    ]
    K = [(mk[i] ^ FK[i]) & 0xFFFFFFFF for i in range(4)]
    for i in range(32):
        Ki = (K[i] ^ _T_key(K[i + 1] ^ K[i + 2] ^ K[i + 3] ^ CK[i])) & 0xFFFFFFFF
        K.append(Ki)
    return K[4:]


def sm4_encrypt_block(ks: list[int], block: bytes) -> bytes:
    if len(block) != 16:
        raise ValueError("SM4 块大小必须为 16 字节")
    X = [
        int.from_bytes(block[0:4], "big"),
        int.from_bytes(block[4:8], "big"),
        int.from_bytes(block[8:12], "big"),
        int.from_bytes(block[12:16], "big"),
    ]
    for i in range(32):
        tmp = X[i] ^ _T(X[i + 1] ^ X[i + 2] ^ X[i + 3] ^ ks[i])
        X.append(tmp & 0xFFFFFFFF)
    # 反序输出
    return (
        X[35].to_bytes(4, "big")
        + X[34].to_bytes(4, "big")
        + X[33].to_bytes(4, "big")
        + X[32].to_bytes(4, "big")
    )


def sm4_cbc_encrypt(key: bytes, iv: bytes, data: bytes) -> bytes:
    if len(key) != 16:
        raise ValueError("SM4 密钥长度必须为 16 字节")
    if len(iv) != 16:
        raise ValueError("SM4 IV 长度必须为 16 字节")
    if len(data) % 16 != 0:
        raise ValueError("SM4-CBC 明文长度必须为 16 的倍数（请先做 PKCS7 填充）")

    ks = sm4_key_schedule(key)
    out = bytearray()
    prev = iv
    for offset in range(0, len(data), 16):
        block = data[offset : offset + 16]
        xored = bytes(a ^ b for a, b in zip(block, prev))
        cipher_block = sm4_encrypt_block(ks, xored)
        out.extend(cipher_block)
        prev = cipher_block
    return bytes(out)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="使用 SM4-CBC+PKCS7 加密 enterprise_dump.json，生成密文文件供 /api/python-from-files 示例使用。",
    )
    parser.add_argument(
        "--input",
        dest="input_path",
        default=os.path.join(DATA_DIR, "enterprise_dump.json"),
        help="明文 JSON 输入文件路径，默认 examples/data/enterprise_dump.json",
    )
    parser.add_argument(
        "--output",
        dest="output_path",
        default=os.path.join(DATA_DIR, "enterprise_dump_encrypted.bin"),
        help="密文输出文件路径，默认 examples/data/enterprise_dump_encrypted.bin",
    )
    parser.add_argument(
        "--key-hex",
        dest="key_hex",
        help="可选：16 字节密钥的 hex 表示（32 个十六进制字符）。不指定则随机生成并打印。",
    )
    return parser.parse_args()


def _parse_or_generate_key(key_hex: str | None) -> Tuple[bytes, str]:
    import secrets

    if key_hex is None:
        key = secrets.token_bytes(16)
        key_hex = key.hex().upper()
    else:
        key_hex = key_hex.strip()
        if len(key_hex) != 32:
            raise ValueError("key-hex 必须是 32 个十六进制字符（表示 16 字节）")
        key = bytes.fromhex(key_hex)

    return key, key_hex


def main() -> None:
    args = parse_args()

    if not os.path.isfile(args.input_path):
        print(f"未找到输入文件: {args.input_path}", file=sys.stderr)
        sys.exit(1)

    try:
        if args.key_hex is None:
            key = bytes.fromhex(TEST_KEY_HEX)
            key_hex = TEST_KEY_HEX
        else:
            key, key_hex = _parse_or_generate_key(args.key_hex)
    except Exception as e:
        print(f"解析 key-hex 失败: {e}", file=sys.stderr)
        sys.exit(1)

    with open(args.input_path, "rb") as f:
        plaintext = f.read()

    padded = _pkcs7_pad(plaintext, 16)

    # 测试用写死 IV，写在输出文件最前面，供 sandbox runner 解密时使用
    iv = bytes.fromhex(TEST_IV_HEX)
    cipher = sm4_cbc_encrypt(key, iv, padded)

    os.makedirs(os.path.dirname(args.output_path), exist_ok=True)
    with open(args.output_path, "wb") as f_out:
        f_out.write(iv + cipher)

    print("加密完成。")
    print(f"明文文件: {args.input_path}")
    print(f"密文文件: {args.output_path}")
    print(f"key_hex: {key_hex}")
    print()
    print("你可以使用以下命令进行测试（在项目根目录、Windows PowerShell）：")
    print("  python examples\\run_python_from_files.py ^")
    print(f"    --data {args.output_path} ^")
    print("    --model examples\\models\\enterprise_aggregate_model.py ^")
    print(f"    --key {key_hex}")


if __name__ == "__main__":
    main()

