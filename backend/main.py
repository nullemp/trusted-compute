from fastapi import FastAPI, File, Form, HTTPException, Depends, status, UploadFile, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from typing import List, Optional
import json
import os
import uvicorn

from database import engine, get_db, Base
from models import Project, Participant, Task, TaskResult
from schemas import (
    ProjectCreate, ProjectResponse, ProjectJoinRequest,
    TaskCreate, TaskResponse, TaskExecuteRequest, TaskResultResponse, TaskResultDecryptedResponse,
    ExecuteSqlRequest,
)
from services import (
    project_service, task_service, sandbox_service,
    execute_sql_service,
    run_analysis_service,
    encryption_service, data_masking_service
)

# Create tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="可信模型计算平台 API",
    description="Trusted Compute Platform API",
    version="1.0.0"
)

# CORS middleware（集成到客户端同源访问时可收紧 allow_origins）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)



# ==================== 直接执行 SQL（无项目/任务，脚本调用）====================

@app.post("/api/execute-sql")
async def execute_sql(req: ExecuteSqlRequest):
    """
    接收数据 + SQL：将数据插入 MariaDB 临时表后执行 SQL，返回结果。
    支持大数据量（临时表在库中，不占应用内存）。不创建项目/任务。
    """
    result = execute_sql_service.execute_sql_mariadb(
        data=req.data,
        sql=req.sql,
        table_name=req.table_name or "input_data",
        columns=req.columns,
    )
    return result


@app.post("/api/execute-sql/file")
async def execute_sql_file(
    file: UploadFile = File(..., description="CSV 文件（支持亿行级，由 MariaDB LOAD DATA 入库）"),
    sql: str = Form(..., description="导入后要执行的 SQL，可查询表 input_data"),
    table_name: str = Form("input_data", description="临时表名"),
    has_header: bool = Form(True, description="首行是否为列名"),
    delimiter: str = Form(",", description="列分隔符，单字符"),
    columns: Optional[str] = Form(None, description="列名，逗号分隔；不填则从首行推断（无 DDL 时）"),
    ddl: Optional[str] = Form(None, description="表结构：CREATE TABLE 括号内部分，如 id INT, value DECIMAL(10,2), name VARCHAR(100)；CSV 列顺序须与 DDL 一致"),
):
    """
    上传 CSV + SQL：用 MariaDB LOAD DATA LOCAL INFILE 导入临时表后执行 SQL。
    不将文件读入应用内存，支持亿行级数据。可选传 ddl 指定列名与类型，不传则从首行推断且列为 TEXT。
    """
    upload_dir = execute_sql_service.UPLOAD_DIR
    os.makedirs(upload_dir, exist_ok=True)
    suffix = os.path.splitext(file.filename or "")[1] or ".csv"
    safe_name = f"{os.urandom(8).hex()}{suffix}"
    file_path = os.path.join(upload_dir, safe_name)
    try:
        with open(file_path, "wb") as f:
            while chunk := await file.read(1024 * 1024):
                f.write(chunk)
        columns_list = [c.strip() for c in columns.split(",") if c.strip()] if (columns and columns.strip()) else None
        if len(delimiter) != 1:
            delimiter = "\t" if delimiter.strip().lower() in ("\\t", "tab") else ","
        result = execute_sql_service.execute_sql_from_file(
            file_path=file_path,
            sql=sql,
            table_name=table_name or "input_data",
            has_header=has_header,
            delimiter=delimiter,
            columns_override=columns_list,
            ddl=ddl.strip() if ddl and ddl.strip() else None,
        )
        return result
    finally:
        if os.path.isfile(file_path):
            try:
                os.remove(file_path)
            except Exception:
                pass


@app.post("/api/execute-sql/files")
async def execute_sql_files(
    config: Optional[str] = Form(None, description='JSON 字符串；也可用 config_file 上传 JSON 文件'),
    config_file: Optional[UploadFile] = File(None, description="或上传 JSON 文件作为 config（curl -F config=@xxx.json 时用）"),
    ddl_file: Optional[UploadFile] = File(None, description="可选：从数据库导出的 DDL 文件（如 schema.sql），表结构以此为准，覆盖 config 中的 ddl"),
    files: List[UploadFile] = File(..., description="多个 CSV，顺序与 config.tables 一致"),
):
    """
    多表上传：多个 CSV 分别导入多个临时表（同连接），再执行一条 SQL（可连表）。
    config.tables[i] 对应 files[i]。每表可指定 table_name、ddl、has_header、delimiter、columns。
    若上传 ddl_file（从数据库导出的 schema.sql），则用其解析出的表定义覆盖 config 中对应表的 ddl。
    """
    if config_file and config_file.filename:
        config = (await config_file.read()).decode("utf-8", errors="replace")
    if not config or not config.strip():
        return {"status": "error", "error": "请提供 config（Form 字符串）或 config_file（JSON 文件）"}
    try:
        conf = json.loads(config)
    except Exception as e:
        return {"status": "error", "error": f"config 非合法 JSON: {e}"}
    tables = conf.get("tables")
    sql = conf.get("sql")
    if not isinstance(tables, list) or not tables:
        return {"status": "error", "error": "config 需包含 tables 数组且非空"}
    if not sql or not isinstance(sql, str):
        return {"status": "error", "error": "config 需包含 sql 字符串"}
    if len(files) != len(tables):
        return {"status": "error", "error": f"文件数量({len(files)})与 tables 数量({len(tables)})不一致"}

    if ddl_file and ddl_file.filename:
        ddl_content = (await ddl_file.read()).decode("utf-8", errors="replace")
        ddl_by_table = execute_sql_service.parse_ddl_file(ddl_content)
        for t in tables:
            tname = (t.get("table_name") or "").strip()
            if tname and tname in ddl_by_table:
                t["ddl"] = ddl_by_table[tname]

    upload_dir = execute_sql_service.UPLOAD_DIR
    os.makedirs(upload_dir, exist_ok=True)
    paths = []
    try:
        for i, uf in enumerate(files):
            suffix = os.path.splitext(uf.filename or "")[1] or ".csv"
            path = os.path.join(upload_dir, f"{os.urandom(8).hex()}_{i}{suffix}")
            paths.append(path)
            with open(path, "wb") as f:
                while chunk := await uf.read(1024 * 1024):
                    f.write(chunk)
        # 归一化 delimiter：多字符时转成 \t 或 ,
        for t in tables:
            d = t.get("delimiter", ",")
            if isinstance(d, str) and len(d) != 1:
                t["delimiter"] = "\t" if d.strip().lower() in ("\\t", "tab") else ","
        result = execute_sql_service.execute_sql_from_files(
            file_paths=paths,
            table_configs=tables,
            sql=sql,
        )
        return result
    finally:
        for p in paths:
            if os.path.isfile(p):
                try:
                    os.remove(p)
                except Exception:
                    pass


# ==================== 客户端调用：DDL + 数据文件 + SQL/Python 分析（无需前端）====================

@app.post("/api/run-analysis")
async def run_analysis(
    config: Optional[str] = Form(None, description='JSON 字符串；也可用 config_file 上传 JSON 文件'),
    config_file: Optional[UploadFile] = File(None, description="或上传 JSON 文件作为 config（curl -F config=@xxx.json 时用）"),
    files: List[UploadFile] = File(..., description="数据文件，顺序与 config.tables 一致"),
    ddl: Optional[str] = Form(None, description="DDL 文本（建库/建表等），可选"),
    ddl_file: Optional[UploadFile] = File(None, description="或上传 DDL 文件，与 ddl 二选一"),
):
    """
    客户端进程调用：先执行 DDL（建库/建表），再按 config 将数据文件导入对应表，最后执行 SQL 或 Python 分析。
    - config 可为 Form 字符串，或通过 config_file 上传 JSON 文件（如 curl -F config=@config.json）。
    - ddl 或 ddl_file：建库、建表等 SQL（可选）。
    - config.tables：每表 table_name、has_header、delimiter、ddl、columns 等，与 files 顺序一致。
    - config.analysis_type：sql | python。
    - config.sql：分析用 SQL（analysis_type=sql 时必填；python 时可选作 data_sql）。
    - config.python：分析用 Python 代码（analysis_type=python 时必填），需定义 result。
    - config.data_sql：analysis_type=python 时，用该 SQL 取数传入 input_params['data']；不填则用 sql 或 SELECT * FROM 第一张表。
    """
    if config_file and config_file.filename:
        config = (await config_file.read()).decode("utf-8", errors="replace")
    if not config or not config.strip():
        return {"status": "error", "error": "请提供 config（Form 字符串）或 config_file（JSON 文件）"}
    try:
        conf = json.loads(config)
    except Exception as e:
        return {"status": "error", "error": f"config 非合法 JSON: {e}"}
    tables = conf.get("tables")
    if not isinstance(tables, list) or not tables:
        return {"status": "error", "error": "config 需包含 tables 数组且非空"}
    if len(files) != len(tables):
        return {"status": "error", "error": f"文件数量({len(files)})与 tables 数量({len(tables)})不一致"}

    ddl_text = None
    if ddl_file and ddl_file.filename:
        ddl_text = (await ddl_file.read()).decode("utf-8", errors="replace")
    elif ddl and ddl.strip():
        ddl_text = ddl.strip()

    upload_dir = execute_sql_service.UPLOAD_DIR
    os.makedirs(upload_dir, exist_ok=True)
    paths = []
    try:
        for i, uf in enumerate(files):
            suffix = os.path.splitext(uf.filename or "")[1] or ".csv"
            path = os.path.join(upload_dir, f"run_analysis_{os.urandom(8).hex()}_{i}{suffix}")
            paths.append(path)
            with open(path, "wb") as f:
                while chunk := await uf.read(1024 * 1024):
                    f.write(chunk)
        for t in tables:
            d = t.get("delimiter", ",")
            if isinstance(d, str) and len(d) != 1:
                t["delimiter"] = "\t" if d.strip().lower() in ("\\t", "tab") else ","
        result = run_analysis_service.run_analysis(
            ddl_text=ddl_text,
            table_configs=tables,
            file_paths=paths,
            analysis_type=conf.get("analysis_type", "sql"),
            analysis_sql=conf.get("sql"),
            analysis_python=conf.get("python"),
            data_sql=conf.get("data_sql"),
        )
        return result
    finally:
        for p in paths:
            if os.path.isfile(p):
                try:
                    os.remove(p)
                except Exception:
                    pass


# ==================== 项目管理 ====================

@app.post("/api/projects", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(project: ProjectCreate, db: Session = Depends(get_db)):
    """创建可信模型计算项目"""
    return project_service.create_project(db, project)


@app.get("/api/projects", response_model=List[ProjectResponse])
async def list_projects(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """获取项目列表"""
    return project_service.list_projects(db, skip=skip, limit=limit)


@app.get("/api/projects/{project_id}", response_model=ProjectResponse)
async def get_project(project_id: int, db: Session = Depends(get_db)):
    """获取项目详情"""
    project = project_service.get_project(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    return project


@app.post("/api/projects/{project_id}/join", response_model=ProjectResponse)
async def join_project(
    project_id: int, 
    request: ProjectJoinRequest, 
    db: Session = Depends(get_db)
):
    """加入项目（审批加入请求）"""
    return project_service.join_project(db, project_id, request)


@app.get("/api/projects/{project_id}/participants")
async def list_participants(project_id: int, db: Session = Depends(get_db)):
    """获取项目参与者列表"""
    return project_service.list_participants(db, project_id)


# ==================== 计算任务管理 ====================

@app.post("/api/projects/{project_id}/tasks", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
async def create_task(
    project_id: int,
    task: TaskCreate,
    db: Session = Depends(get_db)
):
    """创建计算任务"""
    return task_service.create_task(db, project_id, task)


@app.get("/api/projects/{project_id}/tasks", response_model=List[TaskResponse])
async def list_tasks(project_id: int, db: Session = Depends(get_db)):
    """获取项目的计算任务列表"""
    return task_service.list_tasks(db, project_id)


@app.get("/api/tasks/{task_id}", response_model=TaskResponse)
async def get_task(task_id: int, db: Session = Depends(get_db)):
    """获取计算任务详情"""
    task = task_service.get_task(db, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    return task


@app.post("/api/tasks/{task_id}/execute", response_model=TaskResultResponse)
async def execute_task(
    task_id: int,
    execute_request: TaskExecuteRequest,
    db: Session = Depends(get_db)
):
    """执行计算任务"""
    # 1. 获取任务信息
    task = task_service.get_task(db, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    # 2. 在数据沙箱中执行
    raw_result = sandbox_service.execute_task(db, task, execute_request.input_params)
    
    execution_time = raw_result.pop("execution_time", None)
    
    # 3. 数据脱敏
    masked_result = data_masking_service.mask_data(raw_result, task.output_config)
    
    # 4. 加密结果
    encrypted_result = encryption_service.encrypt_result(masked_result)
    
    # 5. 保存结果
    result = task_service.save_result(db, task_id, encrypted_result, execution_time)
    
    return result


@app.get("/api/tasks/{task_id}/results", response_model=List[TaskResultResponse])
async def get_task_results(task_id: int, db: Session = Depends(get_db)):
    """获取任务执行结果列表"""
    return task_service.get_task_results(db, task_id)


@app.get("/api/tasks/{task_id}/results/{result_id}", response_model=TaskResultResponse)
async def get_task_result(task_id: int, result_id: int, db: Session = Depends(get_db)):
    """获取任务执行结果详情（密文）"""
    result = task_service.get_result(db, result_id)
    if not result or result.task_id != task_id:
        raise HTTPException(status_code=404, detail="结果不存在")
    return result


@app.get("/api/tasks/{task_id}/results/{result_id}/decrypt", response_model=TaskResultDecryptedResponse)
async def decrypt_task_result(task_id: int, result_id: int, db: Session = Depends(get_db)):
    """解密并获取任务执行结果（明文，已脱敏）- 授权用户可查看"""
    result = task_service.get_result(db, result_id)
    if not result or result.task_id != task_id:
        raise HTTPException(status_code=404, detail="结果不存在")
    
    # 解密结果
    decrypted_data = encryption_service.decrypt_result(result.encrypted_result)
    
    return TaskResultDecryptedResponse(
        id=result.id,
        task_id=result.task_id,
        result=decrypted_data,
        result_hash=result.result_hash,
        execution_time=result.execution_time,
        created_at=result.created_at
    )


# 集成到客户端：将前端 build 放到 backend/static（或设 STATIC_DIR），后端同时提供 API + 页面
_static_dir = os.getenv("STATIC_DIR") or os.path.join(os.path.dirname(__file__), "static")
if os.path.isdir(_static_dir) and os.path.isfile(os.path.join(_static_dir, "index.html")):
    app.mount("/", StaticFiles(directory=_static_dir, html=True), name="static")

    @app.exception_handler(404)
    async def _spa_fallback(request: Request, exc):
        if request.url.path.startswith("/api"):
            raise exc
        index_path = os.path.join(_static_dir, "index.html")
        if os.path.isfile(index_path):
            return FileResponse(index_path)
        raise exc
else:
    @app.get("/")
    async def root():
        return {"message": "可信模型计算平台 API", "version": "1.0.0"}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
