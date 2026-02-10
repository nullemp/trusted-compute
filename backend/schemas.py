from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List, Union
from datetime import datetime
from models import ProjectStatus, ParticipantStatus, TaskStatus


# ==================== Direct SQL execution (no project/task) ====================

class ExecuteSqlRequest(BaseModel):
    """Accept data + SQL: insert into MariaDB temp table, run SQL, return result (supports large data)."""
    data: List[Union[List[Any], Dict[str, Any]]] = Field(..., description="Table data: each row list or dict")
    sql: str = Field(..., description="SQL to run; can query inserted table (default name input_data)")
    table_name: Optional[str] = Field("input_data", description="Temp table name, alphanumeric and underscore only")
    columns: Optional[List[str]] = Field(None, description="Column names; required when data is list; inferred from first row for list of dict")


# ==================== Project related ====================

class ProjectCreate(BaseModel):
    name: str = Field(..., description="Project name")
    description: Optional[str] = Field(None, description="Project description")
    owner_id: str = Field(..., description="Project owner ID")
    data_config: Optional[Dict[str, Any]] = Field(None, description="Data config")


class ProjectJoinRequest(BaseModel):
    participant_id: str = Field(..., description="Participant ID")
    participant_name: str = Field(..., description="Participant name")
    data_resource: Optional[Dict[str, Any]] = Field(None, description="Data resource info")


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


# ==================== Task related ====================

class TaskCreate(BaseModel):
    name: str = Field(..., description="Task name")
    description: Optional[str] = Field(None, description="Task description")
    model_type: str = Field(..., description="Model type: sql or python")
    model_code: str = Field(..., description="SQL or Python script code")
    input_params: Optional[Dict[str, Any]] = Field(None, description="Input params")
    output_config: Optional[Dict[str, Any]] = Field(None, description="Output config (masking rules etc.)")
    created_by: Optional[str] = Field(None, description="Creator ID")


class TaskExecuteRequest(BaseModel):
    input_params: Dict[str, Any] = Field(..., description="Input params for task execution")


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
    encrypted_result: str = Field(..., description="Encrypted result ciphertext")
    result_hash: Optional[str]
    execution_time: Optional[int]
    created_at: datetime

    class Config:
        from_attributes = True


class TaskResultDecryptedResponse(BaseModel):
    """Decrypted result (masked plaintext)"""
    id: int
    task_id: int
    result: Dict[str, Any] = Field(..., description="Decrypted result data (masked)")
    result_hash: Optional[str]
    execution_time: Optional[int]
    created_at: datetime
