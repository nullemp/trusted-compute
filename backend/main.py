from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import os
import uvicorn

from fastapi import HTTPException

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


# 可选：挂载前端静态资源
_static_dir = os.getenv("STATIC_DIR") or os.path.join(os.path.dirname(__file__), "static")
if os.path.isdir(_static_dir) and os.path.isfile(os.path.join(_static_dir, "index.html")):
    app.mount("/", StaticFiles(directory=_static_dir, html=True), name="static")
else:
    # 无前端时根路径已由上面 GET / 处理，此处不重复
    pass

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
