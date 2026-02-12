from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field


JsonRow = Union[List[Any], Dict[str, Any]]


class TableSpec(BaseModel):
    table_name: str = Field(..., description="表名")
    data: List[JsonRow] = Field(..., description="表数据：每行 list 或 dict")
    columns: Optional[List[str]] = Field(
        None, description="列名；不填则从 dict key 或第一行长度推断"
    )


class ExecuteSqlRequest(BaseModel):
    """沙箱 SQL 请求：支持 DDL 建表 + 多表数据（tables）或单表（data）。"""

    sql: str = Field(..., description="要执行的 SQL 语句")
    ddl: Optional[str] = Field(
        None, description="可选：建表 DDL（如 dbprofile.sql 内容）；提供时先执行 DDL，再按 tables 插入数据（不自动建表）"
    )
    # 单表模式
    data: Optional[List[JsonRow]] = Field(
        None, description="单表数据；与 table_name/columns 搭配使用"
    )
    table_name: Optional[str] = Field(
        "input_data", description="单表模式下的表名，默认 input_data"
    )
    columns: Optional[List[str]] = Field(
        None, description="单表模式下的列名；可选"
    )
    # 多表模式
    tables: Optional[List[TableSpec]] = Field(
        None, description="多表模式：每个元素包含 table_name + data(+columns)"
    )


class ExecutePythonRequest(BaseModel):
    """沙箱 Python 请求：传入代码和输入参数。"""

    code: str = Field(..., description="Python 代码，需在末尾设置 result 变量")
    input_params: Dict[str, Any] = Field(
        default_factory=dict, description="传入沙箱的参数，在代码中通过 input_params 使用"
    )
