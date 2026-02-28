from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi import HTTPException, UploadFile, File, Form
import os
import uvicorn
import json

from schemas import ExecuteSqlRequest, ExecutePythonRequest
from services import sandbox_service
from services.sandbox_db_lifecycle import create_sandbox, destroy_sandbox, sandbox_exists

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


@app.get("/")
async def root():
    return {"message": "Trusted Compute Sandbox API", "version": "1.0.0"}


@app.post("/api/sandboxes")
async def api_create_sandbox():
    """
    创建沙箱（实例隔离）：启动独立 MariaDB 容器并绑定数据卷，返回沙箱 ID。
    销毁时请调用 DELETE /api/sandboxes/{sandbox_id}，将删除容器与卷。
    """
    sandbox_id, err = create_sandbox()
    if err:
        raise HTTPException(status_code=500, detail=err)
    return {"sandbox_id": sandbox_id}


@app.delete("/api/sandboxes/{sandbox_id}")
async def api_destroy_sandbox(sandbox_id: str):
    """销毁沙箱：停止并删除 DB 容器，删除关联数据卷。"""
    ok, err = destroy_sandbox(sandbox_id)
    if not ok:
        raise HTTPException(status_code=400, detail=err or "销毁失败")
    return {"status": "ok", "sandbox_id": sandbox_id}


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
    # 可选：对称加密场景下传入的明文密钥（例如 SM4-CBC），由 sandbox 内完成解密
    key_hex: str | None = Form(
        default=None,
        description="可选：对称密钥（16 字节 hex 编码，表示 16 字节 key），存在时 data_file 视为加密后的原始字节流，由 sandbox 内完成解密",
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

    return sandbox_service.execute_python(code=code, input_params=input_params)


# 可选：挂载前端静态资源
_static_dir = os.getenv("STATIC_DIR") or os.path.join(os.path.dirname(__file__), "static")
if os.path.isdir(_static_dir) and os.path.isfile(os.path.join(_static_dir, "index.html")):
    app.mount("/", StaticFiles(directory=_static_dir, html=True), name="static")
else:
    # 无前端时根路径已由上面 GET / 处理，此处不重复
    pass

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
