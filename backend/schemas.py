from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime
from models import ProjectStatus, ParticipantStatus, TaskStatus


# ==================== 项目相关 ====================

class ProjectCreate(BaseModel):
    name: str = Field(..., description="项目名称")
    description: Optional[str] = Field(None, description="项目描述")
    owner_id: str = Field(..., description="项目创建者ID")
    data_config: Optional[Dict[str, Any]] = Field(None, description="数据配置信息")


class ProjectJoinRequest(BaseModel):
    participant_id: str = Field(..., description="参与者ID")
    participant_name: str = Field(..., description="参与者名称")
    data_resource: Optional[Dict[str, Any]] = Field(None, description="提供的数据资源信息")


class ProjectResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    owner_id: str
    data_config: Optional[Dict[str, Any]]
    status: ProjectStatus
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ParticipantResponse(BaseModel):
    id: int
    project_id: int
    participant_id: str
    participant_name: Optional[str]
    data_resource: Optional[Dict[str, Any]]
    status: ParticipantStatus
    joined_at: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True


# ==================== 任务相关 ====================

class TaskCreate(BaseModel):
    name: str = Field(..., description="任务名称")
    description: Optional[str] = Field(None, description="任务描述")
    model_type: str = Field(..., description="模型类型: sql 或 python")
    model_code: str = Field(..., description="SQL语句或Python脚本代码")
    input_params: Optional[Dict[str, Any]] = Field(None, description="输入参数定义")
    output_config: Optional[Dict[str, Any]] = Field(None, description="输出配置（脱敏规则等）")
    created_by: Optional[str] = Field(None, description="创建者ID")


class TaskExecuteRequest(BaseModel):
    input_params: Dict[str, Any] = Field(..., description="任务执行所需的输入参数")


class TaskResponse(BaseModel):
    id: int
    project_id: int
    name: str
    description: Optional[str]
    model_type: str
    model_code: str
    input_params: Optional[Dict[str, Any]]
    output_config: Optional[Dict[str, Any]]
    status: TaskStatus
    created_by: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TaskResultResponse(BaseModel):
    id: int
    task_id: int
    encrypted_result: str = Field(..., description="加密后的结果密文")
    result_hash: Optional[str]
    execution_time: Optional[int]
    created_at: datetime

    class Config:
        from_attributes = True


class TaskResultDecryptedResponse(BaseModel):
    """解密后的结果（脱敏后的明文）"""
    id: int
    task_id: int
    result: Dict[str, Any] = Field(..., description="解密后的结果数据（已脱敏）")
    result_hash: Optional[str]
    execution_time: Optional[int]
    created_at: datetime
