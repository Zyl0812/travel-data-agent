from typing import TypedDict

from app.entities.column_info import ColumnInfo
from app.entities.metric_info import MetricInfo
from app.entities.value_info import ValueInfo


class ColumnInfoState(TypedDict):
    name: str
    type: str
    role: str
    examples: list
    description: str
    alias: list[str]


class TableInfoState(TypedDict):
    name: str
    role: str
    description: str
    columns: list[ColumnInfoState]


class MetricInfoState(TypedDict):
    name: str
    description: str
    relevant_columns: list[str]
    alias: list[str]


class DateInfoState(TypedDict):
    date: str
    weekday: str
    quarter: str


class DBInfoState(TypedDict):
    dialect: str
    version: str


class _DataAgentStateRequired(TypedDict):
    query: str  # 用户查询


class DataAgentState(_DataAgentStateRequired, total=False):
    trace_id: str  # 追踪ID，贯穿所有节点
    keywords: list[str]  # 用户查询的关键字
    intent: str  # 用户意图: simple, ranking, trend, compare

    retrieved_columns: list[ColumnInfo]  # 召回的字段信息
    retrieved_values: list[ValueInfo]  # 召回的值信息
    retrieved_metrics: list[MetricInfo]  # 召回的指标信息

    table_infos: list[TableInfoState]  # 表信息
    metric_infos: list[MetricInfoState]  # 指标信息

    date_info: DateInfoState  # 日期信息
    db_info: DBInfoState  # 数据库信息
    enum_values: dict[str, list[str]]  # 枚举值字典
    table_columns: dict[str, list[str]]  # 表字段字典

    sql: str  # 生成的SQL
    sql_correction_count: int  # SQL校正次数

    error: str  # 验证SQL时的错误信息
