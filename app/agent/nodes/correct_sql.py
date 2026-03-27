import yaml
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate
from langgraph.runtime import Runtime

from app.agent.context import DataAgentContext
from app.agent.llm import llm
from app.agent.state import DataAgentState
from app.core.log import logger
from app.prompt.prompt_loader import load_prompt


async def correct_sql(state: DataAgentState, runtime: Runtime[DataAgentContext]):
    writer = runtime.stream_writer
    writer({"type": "progress", "step": "校正SQL", "status": "running"})
    
    # 1. 获取已经写入到状态中的表格、指标、上下文信息、用户问题
    table_infos = state.get("table_infos", [])
    metric_infos = state.get("metric_infos", [])
    date_info = state.get("date_info", {})
    db_info = state.get("db_info", {})
    query = state.get("query", "")
    
    sql = state.get("sql", "")
    error = state.get("error", "")

    # 2. 调用 LLM 基于上述信息生成 SQL
    try:
        prompt = PromptTemplate(
            template=load_prompt("correct_sql"),
            input_variables=[
                "query",
                "table_infos",
                "metric_infos",
                "date_info",
                "db_info",
                "sql",
                "error",
            ],
        )
        output_parser = StrOutputParser()

        chain = prompt | llm | output_parser

        corrected_sql = await chain.ainvoke(
            {
                "query": query,
                "table_infos": yaml.dump(
                    table_infos, allow_unicode=True, sort_keys=False
                ),
                "metric_infos": yaml.dump(
                    metric_infos, allow_unicode=True, sort_keys=False
                ),
                "date_info": yaml.dump(date_info, allow_unicode=True, sort_keys=False),
                "db_info": yaml.dump(db_info, allow_unicode=True, sort_keys=False),
                "sql": sql,
                "error": error,
            }
        )

        writer({"type": "progress", "step": "校正SQL", "status": "success"})
        logger.info(f"校正SQL成功: {corrected_sql}")
        return {"sql": corrected_sql}

    except Exception as e:
        writer({"type": "progress", "step": "校正SQL", "status": "error"})
        logger.error(f"校正SQL失败: {str(e)}")
        raise e