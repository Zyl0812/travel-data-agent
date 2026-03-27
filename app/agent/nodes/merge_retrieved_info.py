from langgraph.runtime import Runtime

from app.agent.context import DataAgentContext
from app.agent.state import (
    ColumnInfoState,
    DataAgentState,
    MetricInfoState,
    TableInfoState,
)
from app.core.log import logger
from app.entities.column_info import ColumnInfo
from app.entities.table_info import TableInfo


async def merge_retrieved_info(
    state: DataAgentState, runtime: Runtime[DataAgentContext]
):
    writer = runtime.stream_writer
    writer({"type": "progress", "step": "合并召回信息", "status": "running"})

    # 已召回信息
    retrieved_columns = state.get("retrieved_columns", [])
    retrieved_values = state.get("retrieved_values", [])
    retrieved_metrics = state.get("retrieved_metrics", [])

    meta_mysql_repository = runtime.context["meta_mysql_repository"]

    # 先将retrieved_columns中的信息按 表名.字段名 -> ColumnInfo 存储
    retrieved_columns_map: dict[str, ColumnInfo] = {
        column.id: column for column in retrieved_columns
    }

    # 合并表信息
    table_infos = []

    try:
        # 补充指标信息中召回到的但未被retrieved_columns收录的字段
        for retrieved_metric in retrieved_metrics:
            for relevant_column_id in retrieved_metric.relevant_columns:
                if relevant_column_id not in retrieved_columns_map:
                    # 操作持久层从 column_id 获取 column
                    metric_column_info: ColumnInfo = await meta_mysql_repository.get_column_info_by_id(
                        relevant_column_id
                    )
                    retrieved_columns_map[relevant_column_id] = metric_column_info

        # 补充字段取值涉及的字段并将取值挂回对应字段的examples里,解决最终生成SQL中where字段的问题
        for retrieve_value in retrieved_values:
            value_column_id = retrieve_value.column_id
            # 如果字段未被收录，补充字段
            if value_column_id not in retrieved_columns_map:
                column_info: ColumnInfo = await meta_mysql_repository.get_column_info_by_id(value_column_id)
                retrieved_columns_map[value_column_id] = column_info
            # 字段值
            column_value = retrieve_value.value
            # 补充字段中的字段值例子，先判断一下避免重复
            if column_value not in retrieved_columns_map[value_column_id].examples:
                retrieved_columns_map[value_column_id].examples.append(column_value)

        # 按表分组并补齐主外键
        table_to_columns: dict[str, list[ColumnInfo]] = {}

        for column_info in retrieved_columns_map.values():
            # 如果字段的 table_id 不在 table_to_columns 中，初始化一个空列表
            table_id = column_info.table_id
            if table_id not in table_to_columns:
                table_to_columns[table_id] = []
            table_to_columns[table_id].append(column_info)

        # 为每个表添加主外键
        for table_id in table_to_columns:
            # 从 table_id 获取主键字段和外键字段
            key_columns: list[
                ColumnInfo
            ] = await meta_mysql_repository.get_key_columns_by_table_id(table_id)
            # 当前表已有的所有列ID
            column_ids = [column_info.id for column_info in table_to_columns[table_id]]
            # 补充主外键
            for key_column in key_columns:
                if key_column.id not in column_ids:
                    table_to_columns[table_id].append(key_column)

        # 将table_id->columns映射 转换为 list[TableInfoState]
        for table_id, columns in table_to_columns.items():
            table: TableInfo = await meta_mysql_repository.get_table_info_by_id(
                table_id
            )
            # 组装column_info_state
            columns = [
                ColumnInfoState(
                    name=column.name,
                    type=column.type,
                    role=column.role,
                    examples=column.examples,
                    description=column.description,
                    alias=column.alias,
                )
                for column in columns
            ]
            # 组装table_info_state
            table_infos.append(
                TableInfoState(
                    name=table.name,
                    role=table.role,
                    description=table.description,
                    columns=columns,
                )
            )

        # 封装指标信息列表
        metric_infos = [
            MetricInfoState(
                name=metric.name,
                description=metric.description,
                relevant_columns=metric.relevant_columns,
                alias=metric.alias,
            )
            for metric in retrieved_metrics
        ]

        writer({"type": "progress", "step": "合并召回信息", "status": "success"})
        logger.info(
            f"合并召回信息: 表信息-{[table_info['name'] for table_info in table_infos]},指标信息-{[metric_info['name'] for metric_info in metric_infos]}"
        )

        return {"table_infos": table_infos, "metric_infos": metric_infos}

    except Exception as e:
        writer({"type": "progress", "step": "合并召回信息", "status": "error"})
        logger.error(f"合并召回信息失败: {str(e)}")
        raise
