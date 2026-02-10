from fastapi import FastAPI, File, Form, HTTPException, Depends, status, UploadFile, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from typing import List, Optional
import json
import os
import time
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
    title="Trusted Compute Platform API",
    description="Trusted Compute Platform API",
    version="1.0.0"
)

# CORS middleware (tighten allow_origins when integrating with same-origin client)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)



# ==================== Direct SQL execution (no project/task, script call) ====================

@app.post("/api/execute-sql")
async def execute_sql(req: ExecuteSqlRequest):
    """
    Accept data + SQL: insert data into MariaDB temp table, run SQL, return result.
    Supports large data (temp table in DB, no app memory). Does not create project/task.
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
    file: UploadFile = File(..., description="CSV file (large scale via MariaDB LOAD DATA)"),
    sql: str = Form(..., description="SQL to run after import; can query table input_data"),
    table_name: str = Form("input_data", description="Temporary table name"),
    has_header: bool = Form(True, description="First row is header"),
    delimiter: str = Form(",", description="Column delimiter, single char"),
    columns: Optional[str] = Form(None, description="Column names, comma-separated; optional, inferred from first row if no DDL"),
    ddl: Optional[str] = Form(None, description="Table DDL: CREATE TABLE body, e.g. id INT, value DECIMAL(10,2); CSV column order must match DDL"),
):
    """
    Upload CSV + SQL: import into temp table via MariaDB LOAD DATA LOCAL INFILE, then run SQL.
    File not loaded into app memory; supports very large data. Optional ddl for column types; else inferred as TEXT.
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
    config: Optional[str] = Form(None, description='JSON string; or upload JSON via config_file'),
    config_file: Optional[UploadFile] = File(None, description="Or upload JSON file as config (e.g. curl -F config=@xxx.json)"),
    ddl_file: Optional[UploadFile] = File(None, description="Optional: DDL file from DB (e.g. schema.sql); overrides config ddl"),
    files: List[UploadFile] = File(..., description="Multiple CSVs, order matches config.tables"),
):
    """
    Multi-table upload: import each CSV into a temp table (same connection), then run one SQL (can join).
    config.tables[i] maps to files[i]. Per-table: table_name, ddl, has_header, delimiter, columns.
    If ddl_file (e.g. schema.sql) is uploaded, its table definitions override config ddl.
    """
    if config_file and config_file.filename:
        config = (await config_file.read()).decode("utf-8", errors="replace")
    if not config or not config.strip():
        return {"status": "error", "error": "Provide config (Form string) or config_file (JSON file)"}
    try:
        conf = json.loads(config)
    except Exception as e:
        return {"status": "error", "error": f"config is not valid JSON: {e}"}
    tables = conf.get("tables")
    sql = conf.get("sql")
    if not isinstance(tables, list) or not tables:
        return {"status": "error", "error": "config must contain non-empty tables array"}
    if not sql or not isinstance(sql, str):
        return {"status": "error", "error": "config must contain sql string"}
    if len(files) != len(tables):
        return {"status": "error", "error": f"File count ({len(files)}) does not match tables count ({len(tables)})"}

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
        # Normalize delimiter: multi-char -> \t or ,
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


# ==================== Client call: DDL + data files + SQL/Python analysis (no frontend) ====================

@app.post("/api/run-analysis")
async def run_analysis(
    config: Optional[str] = Form(None, description='JSON string; or upload JSON via config_file'),
    config_file: Optional[UploadFile] = File(None, description="Or upload JSON file as config (e.g. curl -F config=@xxx.json)"),
    files: List[UploadFile] = File(..., description="Data files, order matches config.tables"),
    ddl: Optional[str] = Form(None, description="DDL text (create DB/tables etc.), optional"),
    ddl_file: Optional[UploadFile] = File(None, description="Or upload DDL file; use either ddl or ddl_file"),
):
    """
    Client process call: run DDL (create DB/tables), import data files per config, then run SQL or Python analysis.
    - config: Form string or JSON file via config_file (e.g. curl -F config=@config.json).
    - ddl or ddl_file: create DB/tables SQL (optional).
    - config.tables: per-table table_name, has_header, delimiter, ddl, columns; order matches files.
    - config.analysis_type: sql | python.
    - config.sql: analysis SQL (required for sql; optional as data_sql for python).
    - config.python: Python code for analysis_type=python; must define result.
    - config.data_sql: for python, SQL to fetch data into input_params['data']; else uses sql or SELECT * FROM first table.
    """
    if config_file and config_file.filename:
        config = (await config_file.read()).decode("utf-8", errors="replace")
    if not config or not config.strip():
        return {"status": "error", "error": "Provide config (Form string) or config_file (JSON file)"}
    try:
        conf = json.loads(config)
    except Exception as e:
        return {"status": "error", "error": f"config is not valid JSON: {e}"}
    tables = conf.get("tables")
    if not isinstance(tables, list) or not tables:
        return {"status": "error", "error": "config must contain non-empty tables array"}
    if len(files) != len(tables):
        return {"status": "error", "error": f"File count ({len(files)}) does not match tables count ({len(tables)})"}

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


# ==================== Project management ====================

@app.post("/api/projects", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(project: ProjectCreate, db: Session = Depends(get_db)):
    """Create trusted compute project"""
    return project_service.create_project(db, project)


@app.get("/api/projects", response_model=List[ProjectResponse])
async def list_projects(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """List projects"""
    return project_service.list_projects(db, skip=skip, limit=limit)


@app.get("/api/projects/{project_id}", response_model=ProjectResponse)
async def get_project(project_id: int, db: Session = Depends(get_db)):
    """Get project detail"""
    project = project_service.get_project(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@app.post("/api/projects/{project_id}/join", response_model=ProjectResponse)
async def join_project(
    project_id: int, 
    request: ProjectJoinRequest, 
    db: Session = Depends(get_db)
):
    """Join project (approve join request)"""
    return project_service.join_project(db, project_id, request)


@app.get("/api/projects/{project_id}/participants")
async def list_participants(project_id: int, db: Session = Depends(get_db)):
    """List project participants"""
    return project_service.list_participants(db, project_id)


# ==================== Task management ====================

@app.post("/api/projects/{project_id}/tasks", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
async def create_task(
    project_id: int,
    task: TaskCreate,
    db: Session = Depends(get_db)
):
    """Create compute task"""
    return task_service.create_task(db, project_id, task)


@app.get("/api/projects/{project_id}/tasks", response_model=List[TaskResponse])
async def list_tasks(project_id: int, db: Session = Depends(get_db)):
    """List project tasks"""
    return task_service.list_tasks(db, project_id)


@app.get("/api/tasks/{task_id}", response_model=TaskResponse)
async def get_task(task_id: int, db: Session = Depends(get_db)):
    """Get task detail"""
    task = task_service.get_task(db, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@app.post("/api/tasks/{task_id}/execute", response_model=TaskResultResponse)
async def execute_task(
    task_id: int,
    execute_request: TaskExecuteRequest,
    db: Session = Depends(get_db)
):
    """Execute compute task"""
    # 1. Get task
    task = task_service.get_task(db, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # 2. Execute: SQL (with data) in MariaDB; SQL (no data) mock; Python in sandbox
    if task.model_type == "sql":
        params = execute_request.input_params or {}
        data = params.get("data")
        if data:
            start = time.time()
            raw_result = execute_sql_service.execute_sql_mariadb(
                data=data,
                sql=task.model_code,
                table_name=params.get("table_name") or "input_data",
                columns=params.get("columns"),
            )
            raw_result["execution_time"] = int(time.time() - start)
        else:
            raw_result = {
                "type": "sql",
                "status": "success",
                "result": {
                    "columns": ["id", "value", "category"],
                    "data": [[1, 100, "A"], [2, 200, "B"], [3, 150, "A"], [4, 300, "C"]],
                    "row_count": 4,
                },
                "execution_time": 0,
            }
    else:
        raw_result = sandbox_service.execute_task(db, task, execute_request.input_params)
    
    execution_time = raw_result.pop("execution_time", None)
    
    # 3. Data masking
    masked_result = data_masking_service.mask_data(raw_result, task.output_config)
    
    # 4. Encrypt result
    encrypted_result = encryption_service.encrypt_result(masked_result)
    
    # 5. Save result
    result = task_service.save_result(db, task_id, encrypted_result, execution_time)
    
    return result


@app.get("/api/tasks/{task_id}/results", response_model=List[TaskResultResponse])
async def get_task_results(task_id: int, db: Session = Depends(get_db)):
    """List task execution results"""
    return task_service.get_task_results(db, task_id)


@app.get("/api/tasks/{task_id}/results/{result_id}", response_model=TaskResultResponse)
async def get_task_result(task_id: int, result_id: int, db: Session = Depends(get_db)):
    """Get task result detail (ciphertext)"""
    result = task_service.get_result(db, result_id)
    if not result or result.task_id != task_id:
        raise HTTPException(status_code=404, detail="Result not found")
    return result


@app.get("/api/tasks/{task_id}/results/{result_id}/decrypt", response_model=TaskResultDecryptedResponse)
async def decrypt_task_result(task_id: int, result_id: int, db: Session = Depends(get_db)):
    """Decrypt and get task result (plaintext, masked) - for authorized users"""
    result = task_service.get_result(db, result_id)
    if not result or result.task_id != task_id:
        raise HTTPException(status_code=404, detail="Result not found")
    
    # Decrypt result
    decrypted_data = encryption_service.decrypt_result(result.encrypted_result)
    
    return TaskResultDecryptedResponse(
        id=result.id,
        task_id=result.task_id,
        result=decrypted_data,
        result_hash=result.result_hash,
        execution_time=result.execution_time,
        created_at=result.created_at
    )


# Integrate with client: put frontend build in backend/static (or set STATIC_DIR); backend serves API + static
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
        return {"message": "Trusted Compute Platform API", "version": "1.0.0"}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
