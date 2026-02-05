from sqlalchemy.orm import Session
from typing import List, Optional
from models import Task, TaskResult, TaskStatus
from schemas import TaskCreate, TaskResponse, TaskResultResponse
import hashlib
import json


class TaskService:
    def create_task(self, db: Session, project_id: int, task_data: TaskCreate) -> Task:
        """创建计算任务"""
        db_task = Task(
            project_id=project_id,
            name=task_data.name,
            description=task_data.description,
            model_type=task_data.model_type,
            model_code=task_data.model_code,
            input_params=task_data.input_params,
            output_config=task_data.output_config,
            created_by=task_data.created_by,
            status=TaskStatus.CREATED
        )
        db.add(db_task)
        db.commit()
        db.refresh(db_task)
        return db_task

    def get_task(self, db: Session, task_id: int) -> Optional[Task]:
        """获取任务"""
        return db.query(Task).filter(Task.id == task_id).first()

    def list_tasks(self, db: Session, project_id: int) -> List[Task]:
        """获取项目的任务列表"""
        return db.query(Task).filter(Task.project_id == project_id).all()

    def save_result(self, db: Session, task_id: int, encrypted_result: str, execution_time: Optional[int] = None) -> TaskResult:
        """保存任务执行结果"""
        # 计算结果哈希
        result_hash = hashlib.sha256(encrypted_result.encode()).hexdigest()

        db_result = TaskResult(
            task_id=task_id,
            encrypted_result=encrypted_result,
            result_hash=result_hash,
            execution_time=execution_time
        )
        db.add(db_result)

        # 更新任务状态
        task = self.get_task(db, task_id)
        if task:
            task.status = TaskStatus.COMPLETED

        db.commit()
        db.refresh(db_result)
        return db_result

    def get_result(self, db: Session, result_id: int) -> Optional[TaskResult]:
        """获取结果"""
        return db.query(TaskResult).filter(TaskResult.id == result_id).first()

    def get_task_results(self, db: Session, task_id: int) -> List[TaskResult]:
        """获取任务的所有结果"""
        return db.query(TaskResult).filter(TaskResult.task_id == task_id).all()
