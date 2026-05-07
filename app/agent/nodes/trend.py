"""趋势分析节点：处理时间序列查询"""

import yaml
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate
from langgraph.runtime import Runtime

from app.agent.context import DataAgentContext
from app.agent.llm import llm
from app.agent.state import DataAgentState
from app.agent.nodes.utils import log_node_execution
from app.agent.nodes.generate_sql import clean_sql_output
from app.core.log import logger
from app.prompt.prompt_loader import load_prompt


@log_node_execution("enhance_trend_sql")
async def enhance_trend_sql(state: DataAgentState, runtime: Runtime[DataAgentContext]):
    """增强趋势分析的SQL生成"""
    writer = runtime.stream_writer
    writer({"type": "progress", "step": "趋势分析增强", "status": "running"})

    try:
        intent = state.get("intent", "simple")
        trace_id = state.get("trace_id", "unknown")
        
        # 只有趋势分析才需要增强
        if intent != "trend":
            writer({"type": "progress", "step": "趋势分析增强", "status": "skip"})
            return {}

        query = state.get("query", "")
        table_infos = state.get("table_infos", [])
        metric_infos = state.get("metric_infos", [])
        date_info = state.get("date_info", {})
        db_info = state.get("db_info", {})
        table_columns = state.get("table_columns", {})

        # 格式化 table_columns
        table_columns_str = ""
        for table_name, columns in table_columns.items():
            table_columns_str += f"- {table_name}: [{', '.join(columns)}]\n"

        # 使用 LLM 生成趋势分析的 SQL
        prompt = PromptTemplate(
            template=load_prompt("generate_trend_sql"),
            input_variables=[
                "query",
                "table_columns",
                "metric_infos",
                "date_info",
                "db_info",
            ],
        )
        output_parser = StrOutputParser()
        chain = prompt | llm | output_parser

        raw_sql = await chain.ainvoke(
            {
                "query": query,
                "table_columns": table_columns_str,
                "metric_infos": yaml.dump(metric_infos, allow_unicode=True, sort_keys=False),
                "date_info": yaml.dump(date_info, allow_unicode=True, sort_keys=False),
                "db_info": yaml.dump(db_info, allow_unicode=True, sort_keys=False),
            }
        )

        # 清理 SQL 输出
        sql = clean_sql_output(raw_sql)

        writer({"type": "progress", "step": "趋势分析增强", "status": "success"})
        logger.info(f"[{trace_id}] 趋势分析SQL生成成功: {sql}")
        return {"sql": sql}

    except Exception as e:
        writer({"type": "progress", "step": "趋势分析增强", "status": "error"})
        logger.error(f"趋势分析增强失败: {str(e)}")
        raise
