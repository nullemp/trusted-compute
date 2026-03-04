"""
Sandbox entry: read JSON from stdin (model_type, model_code, input_params), run, output JSON to stdout.
- model_type=python: run Python script (pandas/numpy)，支持在沙箱内用纯 Python 实现的 SM4-CBC 解密大文件。
- model_type=sql: run SQL in sandbox using MariaDB (one DB per run; data in input_params).
"""
import os
import sys
import json
import uuid
import base64
import binascii

# SQL 模式使用 PyMySQL 连接 MariaDB
try:
    import pymysql
    from pymysql.cursors import DictCursor
except ImportError:
    pymysql = None
    DictCursor = None


def _sanitize_identifier(name: str) -> str:
    return "".join(c for c in name if c.isalnum() or c == "_") or "col"


def _rows_and_cols(data, columns_in=None):
    """从 data 得到列名和行列表。"""
    if not data:
        raise ValueError("data 为空")
    rows = data
    if isinstance(rows[0], dict):
        cols = columns_in or list(rows[0].keys())
        rows = [[r.get(c) for c in cols] for r in rows]
    else:
        rows = [list(r) for r in rows]
        cols = columns_in or [f"col_{i}" for i in range(len(rows[0]))]
    cols = [_sanitize_identifier(c) for c in cols]
    if not cols:
        raise ValueError("列名为空")
    return cols, rows


def _normalize_ddl_for_mariadb(ddl: str) -> str:
    """将 DDL 转为 MariaDB 兼容（INTEGER->INT, REAL->DOUBLE, AUTOINCREMENT->AUTO_INCREMENT）。"""
    s = ddl.strip()
    s = s.replace("INTEGER", "INT")
    s = s.replace("REAL", "DOUBLE")
    s = s.replace("AUTOINCREMENT", "AUTO_INCREMENT")
    return s


def _get_mariadb_connection(db_name: str = None, conn_params: dict = None):
    """连接 MariaDB，可选指定 database。conn_params 优先于环境变量（避免容器 -e 未传入）。"""
    if conn_params:
        host = conn_params.get("host") or os.getenv("MARIADB_HOST", "mariadb")
        port = int(conn_params.get("port") or os.getenv("MARIADB_PORT", "3306"))
        user = conn_params.get("user") or os.getenv("MARIADB_USER", "root")
        password = conn_params.get("password") or os.getenv("MARIADB_PASSWORD", "")
    else:
        host = os.getenv("MARIADB_HOST", "mariadb")
        port = int(os.getenv("MARIADB_PORT", "3306"))
        user = os.getenv("MARIADB_USER", "root")
        password = os.getenv("MARIADB_PASSWORD", "")
    # #region agent log
    try:
        with open("/app/.cursor_debug.log", "a") as _f:
            _f.write(json.dumps({"hypothesisId": "H5", "location": "runner._get_mariadb_connection", "message": "resolved host", "data": {"conn_params_present": conn_params is not None, "host": host}, "timestamp": int(__import__("time").time() * 1000)}) + "\n")
    except Exception:
        pass
    # #endregion
    return pymysql.connect(
        host=host,
        port=port,
        user=user,
        password=password,
        database=db_name,
        charset="utf8mb4",
        cursorclass=DictCursor,
    )


# ===== 纯 Python SM4-CBC 解密（与 C 版 sm4.c 兼容） =====


def _unpad_pkcs7(data: bytes, block_size: int = 16) -> bytes:
    if not data:
        raise ValueError("PKCS7 数据为空")
    if len(data) % block_size != 0:
        raise ValueError("PKCS7 数据长度不是块大小的整数倍")
    pad_len = data[-1]
    if pad_len < 1 or pad_len > block_size:
        raise ValueError("PKCS7 填充长度非法")
    if data[-pad_len:] != bytes([pad_len]) * pad_len:
        raise ValueError("PKCS7 填充内容非法")
    return data[:-pad_len]


_SBOX_TABLE = [
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

_FK = [0xA3B1BAC6, 0x56AA3350, 0x677D9197, 0xB27022DC]
_CK = [
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
    return _SBOX_TABLE[(byte >> 4) & 0x0F][byte & 0x0F]


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


def _sm4_key_schedule(key: bytes) -> list[int]:
    if len(key) != 16:
        raise ValueError("SM4 密钥长度必须为 16 字节")
    mk = [
        int.from_bytes(key[0:4], "big"),
        int.from_bytes(key[4:8], "big"),
        int.from_bytes(key[8:12], "big"),
        int.from_bytes(key[12:16], "big"),
    ]
    K = [(mk[i] ^ _FK[i]) & 0xFFFFFFFF for i in range(4)]
    for i in range(32):
        Ki = (K[i] ^ _T_key(K[i + 1] ^ K[i + 2] ^ K[i + 3] ^ _CK[i])) & 0xFFFFFFFF
        K.append(Ki)
    return K[4:]


def _sm4_encrypt_block(ks: list[int], block: bytes) -> bytes:
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
    return (
        X[35].to_bytes(4, "big")
        + X[34].to_bytes(4, "big")
        + X[33].to_bytes(4, "big")
        + X[32].to_bytes(4, "big")
    )


def _sm4_decrypt_block(ks: list[int], block: bytes) -> bytes:
    # 解密时轮密钥顺序反向
    return _sm4_encrypt_block(list(reversed(ks)), block)


class _Sm4CbcDecryptCtx:
    """
    纯 Python SM4-CBC 解密上下文，支持流式 update/final，与 C 版 sm4_ctx 的行为等价：
    - 内部持有轮密钥（对应 C 版 sk[32]）
    - 维护上一个密文块作为 CBC 链（对应 C 版 iv 演进）
    - 使用缓冲区保存未处理完的 cipher（类似 C 版中作为输入的分块数据）
    - final 阶段对最后一个块做 PKCS7 校验和去填充
    """

    def __init__(self, key: bytes, iv: bytes):
        if len(key) != 16:
            raise ValueError("SM4 密钥长度必须为 16 字节")
        if len(iv) != 16:
            raise ValueError("SM4 IV 长度必须为 16 字节")
        self._ks = _sm4_key_schedule(key)
        self._prev = iv  # 上一个密文块（CBC 链）
        self._buf = bytearray()  # 累积 cipher 数据
        self._finalized = False

    def update(self, data: bytes) -> bytes:
        """
        追加一段密文数据，尽量解密输出，保留最后一个块用于 final 做 PKCS7。
        要求：在所有 update 完成后，整体长度必须是 16 的倍数。
        """
        if self._finalized:
            raise ValueError("SM4-CBC 解密已完成，不能再次 update")
        if not data:
            return b""

        self._buf.extend(data)
        out = bytearray()

        # 保留最后 16 字节给 final 做 padding 校验，所以这里只要缓冲区长度 > 16 就可以处理前面的完全块
        while len(self._buf) > 16:
            block = bytes(self._buf[:16])
            del self._buf[:16]

            plain_block = _sm4_decrypt_block(self._ks, block)
            out_block = bytes(a ^ b for a, b in zip(plain_block, self._prev))
            out.extend(out_block)
            self._prev = block

        return bytes(out)

    def final(self) -> bytes:
        """
        处理缓冲区中剩余的最后一个或多个块，并做 PKCS7 去填充。
        约束：最终缓冲长度必须是 16 的倍数，且至少 16 字节（即至少有一个完整 pad 块）。
        """
        if self._finalized:
            raise ValueError("SM4-CBC 解密已完成，不能再次 final")
        self._finalized = True

        if len(self._buf) == 0:
            # 空输入不合法；按照当前协议，总会至少有一个块（包含 PKCS7 padding）
            raise ValueError("SM4-CBC 缓冲区为空，无法完成解密")
        if len(self._buf) % 16 != 0:
            raise ValueError("SM4-CBC 密文长度必须为 16 的倍数")

        out = bytearray()
        # 此处可以一次性处理剩余的每个 16 字节块
        while len(self._buf) > 0:
            block = bytes(self._buf[:16])
            del self._buf[:16]

            plain_block = _sm4_decrypt_block(self._ks, block)
            out_block = bytes(a ^ b for a, b in zip(plain_block, self._prev))
            out.extend(out_block)
            self._prev = block

        return _unpad_pkcs7(bytes(out), block_size=16)


def _sm4_cbc_decrypt_py(key: bytes, iv: bytes, data: bytes) -> bytes:
    if len(key) != 16:
        raise ValueError("SM4 密钥长度必须为 16 字节")
    if len(iv) != 16:
        raise ValueError("SM4 IV 长度必须为 16 字节")
    if len(data) % 16 != 0:
        raise ValueError("SM4-CBC 密文长度必须为 16 的倍数")

    ctx = _Sm4CbcDecryptCtx(key, iv)
    out = ctx.update(data)
    out += ctx.final()
    return out


def _maybe_decrypt_sm4_from_input_params(input_params: dict) -> dict:
    """
    兼容两种模式：
    - 明文模式：input_params 已经包含 data 字段
    - 加密模式：包含 cipher_b64 / key_hex，需在沙箱内解密得到 JSON，再写回 data 字段

    加密格式约定：
    - cipher_b64 解码后得到字节序列：
      [前 16 字节为 IV] + [后续为 SM4-CBC 密文]
    """
    if "cipher_b64" not in input_params:
        return input_params

    try:
        cipher_b64 = input_params["cipher_b64"]
        key_hex = input_params["key_hex"]
    except KeyError as e:
        raise ValueError(f"缺少字段: {e}") from e

    try:
        cipher_all = base64.b64decode(cipher_b64)
    except binascii.Error as e:
        raise ValueError(f"解析 cipher_b64 失败: {e}") from e

    if len(cipher_all) < 16:
        raise ValueError("SM4 密文长度不足 16 字节，无法解析 IV")

    iv = cipher_all[:16]
    cipher = cipher_all[16:]

    try:
        key = bytes.fromhex(key_hex)
    except ValueError as e:
        raise ValueError(f"解析 key_hex 失败: {e}") from e

    plaintext = _sm4_cbc_decrypt_py(key, iv, cipher)

    try:
        payload = json.loads(plaintext.decode("utf-8"))
    except Exception as e:
        raise ValueError(f"解密后解析 JSON 失败: {e}") from e

    # 与 enterprise_dump.json 对齐：优先使用 data 字段；若不存在则直接传整个 JSON
    input_params = dict(input_params)
    input_params["data"] = payload.get("data", payload)
    return input_params


def _insert_data_into_table(cur, table_name: str, data, columns_in=None):
    """向已存在的表插入数据（不建表）。"""
    cols, rows = _rows_and_cols(data, columns_in)
    table_name = _sanitize_identifier(table_name or "input_data")
    placeholders = ", ".join(["%s"] * len(cols))
    col_list = ",".join(f"`{c}`" for c in cols)
    sql = f'INSERT INTO `{table_name}` ({col_list}) VALUES ({placeholders})'
    for row in rows:
        # Use None for NULL so INT columns accept it; empty string '' causes (1366) in strict mode
        cur.execute(sql, [str(v) if v is not None else None for v in row])


def _create_table_from_data(cur, table_name: str, data, columns_in=None):
    """用 data 创建一张表并插入数据（列类型 VARCHAR(2000)）。"""
    cols, rows = _rows_and_cols(data, columns_in)
    table_name = _sanitize_identifier(table_name or "input_data")
    col_defs = ", ".join(f"`{c}` VARCHAR(2000)" for c in cols)
    cur.execute(f"CREATE TABLE `{table_name}` ({col_defs})")
    placeholders = ", ".join(["%s"] * len(cols))
    col_list = ",".join(f"`{c}`" for c in cols)
    sql = f'INSERT INTO `{table_name}` ({col_list}) VALUES ({placeholders})'
    for row in rows:
        cur.execute(sql, [str(v) if v is not None else None for v in row])


def run_sql(sql: str, input_params: dict) -> dict:
    """
    在沙箱内用 MariaDB 执行 SQL：每请求创建独立 database，执行后删除。
    - 若提供 cipher_b64 + key_hex：先 SM4-CBC 解密（密文前 16 字节为 IV），解析 JSON 得到 ddl/tables/data，再建表插入并执行 sql。
    - 若提供 ddl：先执行 DDL 建表，再按 tables 仅插入数据；否则按 data/tables 自动建表+插入。
    - 单表：input_params 包含 data, table_name, columns
    - 多表：input_params 包含 tables=[{table_name, data, columns?}, ...]
    """
    if not pymysql:
        return {"status": "error", "error": "未安装 pymysql，无法连接 MariaDB"}

    if "cipher_b64" in input_params:
        input_params = _maybe_decrypt_sm4_from_input_params(input_params)
        decrypted = input_params.get("data")
        if isinstance(decrypted, dict):
            for k in ("ddl", "tables", "table_name", "columns", "data"):
                if k in decrypted:
                    input_params[k] = decrypted[k]

    tables = input_params.get("tables")
    data = input_params.get("data")
    ddl = input_params.get("ddl")
    conn_params = input_params.get("_mariadb")
    sql_only = not ddl and not tables and not data
    if sql_only and not (sql and sql.strip()):
        return {"status": "error", "error": "请提供 ddl、data、tables 或完整 sql（如 mysqldump 导出的 DDL+INSERT）"}

    db_name = "sandbox_" + uuid.uuid4().hex[:16]
    conn = None
    try:
        conn = _get_mariadb_connection(db_name=None, conn_params=conn_params)
        cur = conn.cursor()
        cur.execute(f"CREATE DATABASE `{db_name}`")
        cur.close()
        conn.close()

        conn = _get_mariadb_connection(db_name=db_name, conn_params=conn_params)
        cur = conn.cursor()

        if sql_only:
            # 仅 sql：执行整段（如 mysqldump 文件内容 + 一条 SELECT），返回第一条有结果集的结果
            pass
        elif ddl:
            mariadb_ddl = _normalize_ddl_for_mariadb(ddl)
            for stmt in mariadb_ddl.split(";"):
                stmt = stmt.strip()
                if stmt:
                    cur.execute(stmt)
            if tables:
                for t in tables:
                    _insert_data_into_table(
                        cur,
                        table_name=t.get("table_name") or "input_data",
                        data=t.get("data") or [],
                        columns_in=t.get("columns"),
                    )
        elif tables:
            for t in tables:
                _create_table_from_data(
                    cur,
                    table_name=t.get("table_name") or "input_data",
                    data=t.get("data") or [],
                    columns_in=t.get("columns"),
                )
        else:
            _create_table_from_data(
                cur,
                table_name=input_params.get("table_name") or "input_data",
                data=data or [],
                columns_in=input_params.get("columns"),
            )

        # 执行 sql 中的语句；若多条则取第一条有结果集的
        statements = [s.strip() for s in sql.strip().split(";") if s.strip()]
        result_columns = None
        result_rows = None
        row_count = 0
        for stmt in statements:
            cur.execute(stmt)
            if cur.description:
                result_columns = [d[0] for d in cur.description]
                rows_raw = cur.fetchall()
                result_rows = [[row[c] for c in result_columns] for row in rows_raw]
                row_count = len(result_rows)
                break
            row_count = cur.rowcount

        cur.close()
        conn.close()
        conn = None

        # 删除本请求的 database
        conn_drop = _get_mariadb_connection(db_name=None, conn_params=conn_params)
        cur_drop = conn_drop.cursor()
        cur_drop.execute(f"DROP DATABASE IF EXISTS `{db_name}`")
        cur_drop.close()
        conn_drop.close()

        if result_columns is not None:
            return {
                "status": "success",
                "type": "sql",
                "result": {
                    "columns": result_columns,
                    "data": result_rows or [],
                    "row_count": row_count,
                },
            }
        return {
            "status": "success",
            "type": "sql",
            "result": {"row_count": row_count},
        }
    except Exception as e:
        if conn:
            try:
                conn.close()
            except Exception:
                pass
        try:
            _conn = _get_mariadb_connection(db_name=None, conn_params=conn_params)
            _cur = _conn.cursor()
            _cur.execute(f"DROP DATABASE IF EXISTS `{db_name}`")
            _cur.close()
            _conn.close()
        except Exception:
            pass
        return {"status": "error", "error": str(e)}
    finally:
        try:
            _conn = _get_mariadb_connection(db_name=None, conn_params=conn_params)
            _cur = _conn.cursor()
            _cur.execute(f"DROP DATABASE IF EXISTS `{db_name}`")
            _cur.close()
            _conn.close()
        except Exception:
            pass


def run_python(model_code: str, input_params: dict) -> dict:
    import pandas as pd
    import numpy as np

    # 若包含 cipher_b64/key_hex/iv_hex，则在沙箱内先完成 SM4-CBC 解密和 JSON 解析
    try:
        input_params = _maybe_decrypt_sm4_from_input_params(input_params)
    except Exception as e:
        return {"type": "python", "status": "error", "error": f"SM4 解密失败: {e}"}

    local_names = {"input_params": input_params, "pd": pd, "np": np}
    exec(model_code, local_names)
    result = local_names.get("result")
    if result is None:
        return {"type": "python", "status": "error", "error": "未定义 result 变量"}

    if isinstance(result, pd.DataFrame):
        output = {
            "type": "dataframe",
            "columns": result.columns.tolist(),
            "data": result.values.tolist(),
            "shape": list(result.shape),
        }
    elif isinstance(result, dict):
        output = result
    elif isinstance(result, (list, tuple)):
        output = {"type": "list", "data": list(result)}
    else:
        output = {"type": "scalar", "value": str(result)}

    return {"type": "python", "status": "success", "result": output}


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception as e:
        print(json.dumps({"status": "error", "error": f"无效输入 JSON: {e}"}), flush=True)
        sys.exit(1)

    model_type = payload.get("model_type")
    model_code = payload.get("model_code", "")
    input_params = payload.get("input_params") or {}

    try:
        if model_type == "python":
            out = run_python(model_code, input_params)
        elif model_type == "sql":
            out = run_sql(model_code, input_params)
        else:
            out = {"status": "error", "error": f"不支持的 model_type: {model_type}"}
    except Exception as e:
        out = {"status": "error", "error": str(e)}

    print(json.dumps(out, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
