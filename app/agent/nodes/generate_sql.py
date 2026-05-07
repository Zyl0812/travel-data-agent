import re
import yaml
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate
from langgraph.runtime import Runtime

from app.agent.context import DataAgentContext
from app.agent.llm import llm
from app.agent.state import DataAgentState
from app.agent.nodes.utils import log_node_execution
from app.core.log import logger
from app.prompt.prompt_loader import load_prompt


def clean_sql_output(sql: str) -> str:
    """清理SQL输出，移除markdown代码块标记等"""
    # 移除 ```sql 和 ``` 标记
    sql = re.sub(r'```sql\s*', '', sql)
    sql = re.sub(r'```\s*', '', sql)
    # 移除开头和结尾的空白字符
    sql = sql.strip()
    # 移除尾部的分号（EXPLAIN 不需要）
    sql = sql.rstrip(';')
    return sql


@log_node_execution("generate_sql")
async def generate_sql(state: DataAgentState, runtime: Runtime[DataAgentContext]):
    writer = runtime.stream_writer
    writer({"type": "progress", "step": "生成SQL", "status": "running"})

    trace_id = state.get("trace_id", "unknown")

    # 1. 获取已经写入到状态中的表格、指标、上下文信息、用户问题
    table_infos = state.get("table_infos", [])
    metric_infos = state.get("metric_infos", [])
    date_info = state.get("date_info", {})
    db_info = state.get("db_info", {})
    table_columns = state.get("table_columns", {})
    query = state.get("query", "")

    # 2. 将 table_columns 格式化为可读的字符串
    table_columns_str = ""
    for table_name, columns in table_columns.items():
        table_columns_str += f"- {table_name}: [{', '.join(columns)}]\n"

    # 3. 调用 LLM 基于上述信息生成 SQL
    try:
        prompt = PromptTemplate(
            template=load_prompt("generate_sql"),
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
                "metric_infos": yaml.dump(
                    metric_infos, allow_unicode=True, sort_keys=False
                ),
                "date_info": yaml.dump(date_info, allow_unicode=True, sort_keys=False),
                "db_info": yaml.dump(db_info, allow_unicode=True, sort_keys=False),
            }
        )

        # 清理 SQL 输出
        sql = clean_sql_output(raw_sql)

        writer({"type": "progress", "step": "生成SQL", "status": "success"})
        logger.info(f"[{trace_id}] 生成SQL成功: {sql}")
        return {"sql": sql}

    except Exception as e:
        writer({"type": "progress", "step": "生成SQL", "status": "error"})
        logger.error(f"[{trace_id}] 生成SQL失败: {str(e)}")
        raise e
