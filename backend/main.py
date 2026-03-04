from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi import HTTPException, UploadFile, File, Form
import os
import uvicorn
import json
import time
import shutil
from typing import Any, Dict

from schemas import ExecuteSqlRequest, ExecutePythonRequest
from services import sandbox_service
from services.sandbox_db_lifecycle import (
    create_sandbox,
    destroy_sandbox,
    sandbox_exists,
    create_python_sandbox,
    destroy_python_sandbox,
    python_sandbox_exists,
    import_python_sandbox,
    get_python_sandbox_dir,
    create_sql_sandbox,
    destroy_sql_sandbox,
    sql_sandbox_exists,
    import_sql_sandbox,
    get_sql_sandbox_dir,
    sandbox_db_ip,
    sandbox_db_host,
)
from sm4_utils import sm4_cbc_encrypt_py

app = FastAPI(
    title="Trusted Compute Sandbox API",
    description="沙箱计算服务：SQL（MariaDB）与 Python 在沙箱内执行，结果直接返回。",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


RESULTS_ROOT = os.getenv(
    "RESULTS_ROOT",
    os.path.join(os.path.dirname(__file__), "results"),
)


def _mariadb_connection_for_sandbox(db_sandbox_id: str):
    """
    根据 DB 沙箱 ID 返回 (_mariadb, container_env) 供 Python 连库；
    若沙箱不存在或非 DB 沙箱则返回 (None, None)。
    """
    if not db_sandbox_id or not sandbox_exists(db_sandbox_id):
        return None, None
    root_password = os.getenv("MARIADB_ROOT_PASSWORD", "trusted_compute_root")
    host = sandbox_db_ip(db_sandbox_id) or sandbox_db_host(db_sandbox_id)
    _mariadb = {
        "host": host,
        "port": 3306,
        "user": "root",
        "password": root_password,
    }
    container_env = {
        "MARIADB_HOST": host,
        "MARIADB_PORT": "3306",
        "MARIADB_USER": "root",
        "MARIADB_PASSWORD": root_password,
    }
    return _mariadb, container_env


def _encrypt_and_save_result(
    *,
    result_obj: Dict[str, Any],
    sandbox_id: str,
    data_content: bytes,
    key_hex: str,
) -> str:
    """
    将执行结果 JSON 用与数据相同的 key/IV 做 SM4-CBC 加密，并写入结果文件。
    - 结果文件内容格式：与输入数据一致，前 16 字节为 IV，后续为 SM4-CBC 密文。
    - 返回结果文件的绝对路径。
    """
    iv = data_content[:16]
    if len(iv) != 16:
        raise ValueError("数据文件长度不足 16 字节，无法获取 IV")
    try:
        key = bytes.fromhex(key_hex.strip())
    except ValueError as e:
        raise ValueError(f"解析 key_hex 失败: {e}") from e
    cipher_body = sm4_cbc_encrypt_py(key=key, iv=iv, data=json.dumps(result_obj, ensure_ascii=False).encode("utf-8"))
    cipher_all = iv + cipher_body

    sandbox_dir = os.path.join(RESULTS_ROOT, sandbox_id)
    os.makedirs(sandbox_dir, exist_ok=True)
    filename = f"result_{int(time.time() * 1000)}.bin"
    out_path = os.path.join(sandbox_dir, filename)
    with open(out_path, "wb") as f:
        f.write(cipher_all)
    return out_path


@app.get("/")
async def root():
    return {"message": "Trusted Compute Sandbox API", "version": "1.0.0"}


@app.post("/api/sandboxes")
async def api_create_sandbox(
    type: str = Query("db", description="沙箱类型：db=仅 MariaDB，python=Python 沙箱，sql=SQL 沙箱"),
):
    """
    创建沙箱（实例隔离）。
    - type=db：仅启动独立 MariaDB 容器并绑定数据卷（用于直接 execute-sql）。
    - type=python：创建 Python 沙箱 = 工作目录 + 同 id 的 MariaDB（导入 data/model/key 后 run 执行 Python）。
    - type=sql：创建 SQL 沙箱 = 工作目录 + 同 id 的 MariaDB（导入 SQL 脚本后 run 执行 SQL）。
    销毁时请调用 DELETE /api/sandboxes/{sandbox_id}。
    """
    kind = type.strip().lower()
    if kind == "python":
        sandbox_id, err = create_python_sandbox()
    elif kind == "sql":
        sandbox_id, err = create_sql_sandbox()
    else:
        sandbox_id, err = create_sandbox()
    if err:
        return {
            "status": 1,
            "sandbox_id": None,
            "error": err,
        }
    return {
        "status": 0,
        "sandbox_id": sandbox_id,
        "error": "",
    }


@app.post("/api/sandboxes/{sandbox_id}/import")
async def api_import_sandbox(
    sandbox_id: str,
    data_file: UploadFile | None = File(None, description="加密数据文件（前 16 字节 IV + 密文），Python/SQL 沙箱均必填"),
    model_file: UploadFile | None = File(None, description="Python 沙箱为 .py 脚本，SQL 沙箱为 .sql 脚本，均用此参数名"),
    key_hex: str | None = Form(None, description="明文密钥 16 字节 hex，Python/SQL 沙箱均必填"),
):
    """
    导入沙箱。Python 与 SQL 统一使用三参数：data_file、model_file、key_hex。
    - Python 沙箱：model_file 为 Python 计算模型脚本，写入 data.bin / model.py / key_hex.txt。
    - SQL 沙箱：model_file 为 SQL 计算模型脚本，写入 data.bin / script.sql / key_hex.txt。
    """
    if python_sandbox_exists(sandbox_id):
        if data_file is None or model_file is None or key_hex is None:
            return {"status": 1, "sandbox_id": sandbox_id, "error": "Python 沙箱导入需传 data_file、model_file、key_hex"}
        try:
            data_content = await data_file.read()
        except Exception as e:
            return {"status": 1, "sandbox_id": sandbox_id, "error": f"读取 data_file 失败: {e}"}
        try:
            model_content = (await model_file.read()).decode("utf-8")
        except Exception as e:
            return {"status": 1, "sandbox_id": sandbox_id, "error": f"读取 model_file 失败: {e}"}
        ok, err = import_python_sandbox(sandbox_id, data_content, model_content, key_hex)
        if not ok:
            return {"status": 1, "sandbox_id": sandbox_id, "error": err or "导入失败"}
        return {"status": 0, "sandbox_id": sandbox_id, "error": ""}
    if sql_sandbox_exists(sandbox_id):
        if data_file is None or model_file is None or key_hex is None:
            return {"status": 1, "sandbox_id": sandbox_id, "error": "SQL 沙箱导入需传 data_file、model_file、key_hex"}
        try:
            data_content = await data_file.read()
        except Exception as e:
            return {"status": 1, "sandbox_id": sandbox_id, "error": f"读取 data_file 失败: {e}"}
        try:
            model_content = (await model_file.read()).decode("utf-8")
        except Exception as e:
            return {"status": 1, "sandbox_id": sandbox_id, "error": f"读取 model_file 失败: {e}"}
        ok, err = import_sql_sandbox(sandbox_id, data_content, model_content, key_hex)
        if not ok:
            return {"status": 1, "sandbox_id": sandbox_id, "error": err or "导入失败"}
        return {"status": 0, "sandbox_id": sandbox_id, "error": ""}
    return {"status": 1, "sandbox_id": sandbox_id, "error": "沙箱不存在或类型不支持"}


@app.post("/api/sandboxes/{sandbox_id}/run")
async def api_run_sandbox(
    sandbox_id: str,
    db_sandbox_id: str | None = Query(None, description="仅 Python 沙箱：覆盖使用的 DB 沙箱 ID；不传则用本沙箱自带的 MariaDB"),
):
    """
    在已导入的沙箱上执行一次计算。
    - Python 沙箱：使用已导入的 data/model/key 跑 Python，可选 db_sandbox_id 覆盖连库。
    - SQL 沙箱：在该沙箱的 MariaDB 内执行已导入的 script.sql，返回查询结果。
    """
    if sql_sandbox_exists(sandbox_id):
        root = get_sql_sandbox_dir(sandbox_id)
        if not root:
            return {"status": 1, "sandbox_id": sandbox_id, "error": "沙箱目录不可用"}
        data_path = os.path.join(root, "data.bin")
        script_path = os.path.join(root, "script.sql")
        model_py_path = os.path.join(root, "model.py")
        key_path = os.path.join(root, "key_hex.txt")
        if not os.path.isfile(script_path) and os.path.isfile(model_py_path):
            script_path = model_py_path
        missing = [n for n, p in [("data.bin", data_path), ("script.sql 或 model.py", script_path), ("key_hex.txt", key_path)] if not os.path.isfile(p)]
        if missing:
            return {
                "status": 1,
                "sandbox_id": sandbox_id,
                "error": f"SQL 沙箱未完整导入（缺 {', '.join(missing)}），工作目录: {root}",
            }
        try:
            with open(data_path, "rb") as f:
                data_content = f.read()
            with open(script_path, "r", encoding="utf-8") as f:
                sql_content = f.read()
            with open(key_path, "r", encoding="utf-8") as f:
                key_hex = f.read().strip()
        except Exception as e:
            return {"status": 1, "sandbox_id": sandbox_id, "error": str(e)}
        import base64
        cipher_b64 = base64.b64encode(data_content).decode("ascii")
        out = sandbox_service.execute_sql(
            sandbox_id=sandbox_id,
            sql=sql_content,
            cipher_b64=cipher_b64,
            key_hex=key_hex,
        )
        if out.get("status") == "error":
            return {
                "status": 1,
                "path": "",
                "error": out.get("error", "执行失败"),
            }
        try:
            out_path = _encrypt_and_save_result(
                result_obj=out,
                sandbox_id=sandbox_id,
                data_content=data_content,
                key_hex=key_hex,
            )
        except Exception as e:
            return {
                "status": 1,
                "path": "",
                "error": str(e),
            }
        return {
            "status": 0,
            "path": out_path,
        }

    if not python_sandbox_exists(sandbox_id):
        return {
            "status": 1,
            "sandbox_id": sandbox_id,
            "error": "沙箱不存在或未导入",
        }
    root = get_python_sandbox_dir(sandbox_id)
    if not root:
        return {"status": 1, "sandbox_id": sandbox_id, "error": "沙箱目录不可用"}
    data_path = os.path.join(root, "data.bin")
    model_path = os.path.join(root, "model.py")
    key_path = os.path.join(root, "key_hex.txt")
    if not all(os.path.isfile(p) for p in (data_path, model_path, key_path)):
        return {"status": 1, "sandbox_id": sandbox_id, "error": "沙箱未完整导入（缺 data/model/key）"}
    try:
        with open(data_path, "rb") as f:
            data_content = f.read()
        with open(model_path, "r", encoding="utf-8") as f:
            model_content = f.read()
        with open(key_path, "r", encoding="utf-8") as f:
            key_hex = f.read().strip()
    except Exception as e:
        return {"status": 1, "sandbox_id": sandbox_id, "error": str(e)}
    import base64
    cipher_b64 = base64.b64encode(data_content).decode("ascii")
    input_params = {"cipher_b64": cipher_b64, "key_hex": key_hex}
    use_network = False
    container_env = None
    # 优先使用传入的 db_sandbox_id；未传则使用本 Python 沙箱自带的 MariaDB（创建时已绑定同 id 的 DB 容器）
    db_id = db_sandbox_id or sandbox_id
    _mariadb, container_env = _mariadb_connection_for_sandbox(db_id)
    if db_sandbox_id and _mariadb is None:
        return {"status": 1, "sandbox_id": sandbox_id, "error": f"DB 沙箱不存在或不可用: {db_sandbox_id}"}
    if _mariadb is not None:
        input_params["_mariadb"] = _mariadb
        use_network = True
    out = sandbox_service.execute_python(
        code=model_content,
        input_params=input_params,
        use_network=use_network,
        container_env=container_env,
    )
    if out.get("status") == "error":
        return {
            "status": 1,
            "path": "",
            "error": out.get("error", "执行失败"),
        }
    try:
        out_path = _encrypt_and_save_result(
            result_obj=out,
            sandbox_id=sandbox_id,
            data_content=data_content,
            key_hex=key_hex,
        )
    except Exception as e:
        return {
            "status": 1,
            "path": "",
            "error": str(e),
        }
    return {
        "status": 0,
        "path": out_path,
    }


@app.delete("/api/sandboxes/{sandbox_id}")
async def api_destroy_sandbox(sandbox_id: str):
    """销毁沙箱：Python/SQL 沙箱删 MariaDB + 工作目录；仅 DB 沙箱删容器与卷。"""
    if python_sandbox_exists(sandbox_id):
        ok, err = destroy_python_sandbox(sandbox_id)
    elif sql_sandbox_exists(sandbox_id):
        ok, err = destroy_sql_sandbox(sandbox_id)
    elif sandbox_exists(sandbox_id):
        ok, err = destroy_sandbox(sandbox_id)
    else:
        return {
            "status": 1,
            "sandbox_id": sandbox_id,
            "error": "沙箱不存在或已销毁",
        }
    # 无论哪种类型，只要销毁成功，则尝试删除对应的结果目录（若存在）
    if ok:
        results_dir = os.path.join(RESULTS_ROOT, sandbox_id)
        try:
            shutil.rmtree(results_dir)
        except FileNotFoundError:
            pass
        except Exception:
            # 删除结果目录失败不视为整体失败，只在 error 中提示
            err = (err or "") + "（结果目录未完全清理）"
    if not ok:
        return {
            "status": 1,
            "path": "",
            "error": err or "销毁失败",
        }
    return {
        "status": 0,
        "path": "",
    }


@app.post("/api/execute-sql")
async def execute_sql(req: ExecuteSqlRequest):
    """
    在指定沙箱的 MariaDB 中执行 SQL（需先 POST /api/sandboxes 创建沙箱）。
    - 可选 ddl：建表依据，再按 tables 插入数据。
    - 单表：传 data + table_name(可选) + columns(可选)；多表：传 tables=[...]
    """
    tables = [t.model_dump() for t in req.tables] if req.tables is not None else None
    return sandbox_service.execute_sql(
        sandbox_id=req.sandbox_id,
        sql=req.sql,
        ddl=req.ddl,
        data=req.data or [],
        table_name=req.table_name or "input_data",
        columns=req.columns,
        tables=tables,
    )


@app.post("/api/execute-python")
async def execute_python(req: ExecutePythonRequest):
    """在沙箱内执行 Python 代码（pandas/numpy 可用），代码末尾需设置 result 变量，结果直接返回。"""
    return sandbox_service.execute_python(
        code=req.code,
        input_params=req.input_params,
    )


@app.post("/api/python-from-files")
async def execute_python_from_files(
    data_file: UploadFile = File(
        ...,
        description=(
            "数据文件，例如 enterprise_dump.json；"
            "若按 SM4-CBC 加密，则为 [16 字节 IV] + [密文] 的原始字节流"
        ),
    ),
    model_file: UploadFile = File(..., description="Python 计算模型脚本，例如 enterprise_aggregate_model.py"),
    key_hex: str | None = Form(
        default=None,
        description="可选：对称密钥（16 字节 hex 编码），存在时 data_file 视为加密字节流，由 sandbox 内解密",
    ),
    db_sandbox_id: str | None = Form(
        default=None,
        description="可选：DB 沙箱 ID，传入时 Python 模型可通过 input_params['_mariadb'] 连接该 MariaDB",
    ),
):
    """
    从两个文件执行 Python 计算模型：
    - data_file:
        - 默认：JSON，通常与 enterprise_dump.json 结构一致（包含 data 字段）
        - 如果同时提供 key_hex：视为加密后的原始字节流，格式为 [16 字节 IV] + [密文]，不在此处解析 JSON，而是透传给 sandbox
    - model_file: Python 源码；在 sandbox 内执行，需在末尾设置 result 变量
    - key_hex：可选，对称密钥（16 字节 hex 编码），由 sandbox 内代码自行完成解密（例如 SM4-CBC）
    """
    try:
        raw = await data_file.read()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"读取 data_file 失败: {e}")
    try:
        code_bytes = await model_file.read()
        code = code_bytes.decode("utf-8")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"读取 model_file 失败: {e}")

    # 如果未提供对称密钥，保持向后兼容：按 JSON 解析并将 data 字段透传给 sandbox
    if not key_hex:
        try:
            payload = json.loads(raw.decode("utf-8"))
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"解析 data_file 失败: {e}")

        input_params = {
            # 与 enterprise_dump.json 对齐：优先使用 data 字段；若不存在则直接传整个 JSON
            "data": payload.get("data", payload),
        }
    else:
        # 在沙箱内自行解密：此处不解析 JSON，仅将 [IV+密文] 和密钥作为参数传入
        import base64

        cipher_b64 = base64.b64encode(raw).decode("ascii")
        input_params = {
            "cipher_b64": cipher_b64,
            "key_hex": key_hex,
        }

    use_network = False
    container_env = None
    if db_sandbox_id:
        _mariadb, container_env = _mariadb_connection_for_sandbox(db_sandbox_id)
        if _mariadb is not None:
            input_params["_mariadb"] = _mariadb
            use_network = True

    return sandbox_service.execute_python(
        code=code,
        input_params=input_params,
        use_network=use_network,
        container_env=container_env,
    )


# 可选：挂载前端静态资源
_static_dir = os.getenv("STATIC_DIR") or os.path.join(os.path.dirname(__file__), "static")
if os.path.isdir(_static_dir) and os.path.isfile(os.path.join(_static_dir, "index.html")):
    app.mount("/", StaticFiles(directory=_static_dir, html=True), name="static")
else:
    # 无前端时根路径已由上面 GET / 处理，此处不重复
    pass

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
