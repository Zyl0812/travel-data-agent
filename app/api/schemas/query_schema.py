from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel


class ResultType(str, Enum):
    """结果类型枚举"""
    TABLE = "table"  # 普通表格
    TIME_SERIES = "time_series"  # 时间序列
    COMPARISON = "comparison"  # 对比分析
    RANKING = "ranking"  # 排名分析


class QueryRequest(BaseModel):
    """查询请求"""
    query: str


class QueryResponse(BaseModel):
    """查询响应"""
    query: str  # 原始查询
    intent: str  # 识别的意图
    result_type: ResultType  # 结果类型
    sql: str  # 生成的SQL
    columns: list[str]  # 结果列名
    data: list[dict[str, Any]]  # 结果数据
    row_count: int  # 结果行数
    error: Optional[str] = None  # 错误信息（如有）
    tables: list[str] = []  # 识别的表
    metrics: list[str] = []  # 识别的指标