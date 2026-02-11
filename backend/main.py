from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import os
import uvicorn

from schemas import ExecuteSqlRequest, ExecutePythonRequest
from services import sandbox_service

app = FastAPI(
    title="Trusted Compute Sandbox API",
    description="沙箱计算服务：SQL（SQLite）与 Python 在沙箱内执行，结果直接返回，不落盘。",
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


@app.post("/api/execute-sql")
async def execute_sql(req: ExecuteSqlRequest):
    """
    在沙箱内用 SQLite 执行 SQL，结果直接返回。
    - 单表：传 data + table_name(可选) + columns(可选)
    - 多表：传 tables=[{table_name, data, columns?}, ...]
    """
    if req.tables is not None:
        tables = [t.model_dump() for t in req.tables]
        return sandbox_service.execute_sql(
            sql=req.sql,
            tables=tables,
        )
    return sandbox_service.execute_sql(
        sql=req.sql,
        data=req.data or [],
        table_name=req.table_name or "input_data",
        columns=req.columns,
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
