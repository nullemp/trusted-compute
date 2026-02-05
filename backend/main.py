from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List, Optional
import uvicorn

from database import engine, get_db, Base
from models import Project, Participant, Task, TaskResult
from schemas import (
    ProjectCreate, ProjectResponse, ProjectJoinRequest,
    TaskCreate, TaskResponse, TaskExecuteRequest, TaskResultResponse, TaskResultDecryptedResponse
)
from services import (
    project_service, task_service, sandbox_service, 
    encryption_service, data_masking_service
)

# Create tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="可信模型计算平台 API",
    description="Trusted Compute Platform API",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    return {"message": "可信模型计算平台 API", "version": "1.0.0"}


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


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
