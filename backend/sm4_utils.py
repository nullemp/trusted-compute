"""
SM4-CBC 加密工具（供 backend 使用），与 sandbox/runner.py 中的 SM4 实现保持兼容。

仅在需要用「同一明文密钥 + 同一 IV」对结果 JSON 做 SM4-CBC+PKCS7 加密并落盘时使用。
"""
from __future__ import annotations

import math
from typing import ByteString

from sandbox.runner import _sm4_key_schedule, _sm4_encrypt_block


def _pkcs7_pad(data: bytes, block_size: int = 16) -> bytes:
    if block_size <= 0 or block_size > 255:
        raise ValueError("block_size 必须在 1–255 之间")
    pad_len = block_size - (len(data) % block_size)
    if pad_len == 0:
        pad_len = block_size
    return data + bytes([pad_len]) * pad_len


def sm4_cbc_encrypt_py(key: ByteString, iv: ByteString, data: ByteString) -> bytes:
    """
    纯 Python SM4-CBC 加密（与 runner 内解密逻辑对偶）：
    - key: 16 字节 SM4 密钥
    - iv: 16 字节 IV（与加密数据文件前 16 字节一致）
    - data: 明文字节串，内部做 PKCS7 补齐

    返回值为纯 cipher（不包含 IV）；调用方可按需要自行决定是否在文件前拼接 IV。
    """
    key_bytes = bytes(key)
    iv_bytes = bytes(iv)
    if len(key_bytes) != 16:
        raise ValueError("SM4 密钥长度必须为 16 字节")
    if len(iv_bytes) != 16:
        raise ValueError("SM4 IV 长度必须为 16 字节")

    ks = _sm4_key_schedule(key_bytes)
    prev = iv_bytes
    plain = _pkcs7_pad(bytes(data), 16)
    out = bytearray()

    for i in range(0, len(plain), 16):
        block = plain[i : i + 16]
        xored = bytes(a ^ b for a, b in zip(block, prev))
        cipher_block = _sm4_encrypt_block(ks, xored)
        out.extend(cipher_block)
        prev = cipher_block

    return bytes(out)

