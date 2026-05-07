from langgraph.runtime import Runtime

from app.agent.context import DataAgentContext
from app.agent.state import DataAgentState
from app.agent.nodes.utils import log_node_execution
from app.core.log import logger


@log_node_execution("execute_sql")
async def execute_sql(state: DataAgentState, runtime: Runtime[DataAgentContext]):
    writer = runtime.stream_writer
    writer({"type": "progress", "step": "执行SQL", "status": "running"})

    trace_id = state.get("trace_id", "unknown")
    sql = state.get("sql", "")
    error = state.get("error", "")

    # 如果已经有错误（如校正失败），直接返回错误
    if error:
        writer({"type": "progress", "step": "执行SQL", "status": "error"})
        writer({"type": "result", "data": [], "error": error})
        logger.error(f"[{trace_id}] 跳过SQL执行，已有错误: {error}")
        return {}

    dw_mysql_repository = runtime.context["dw_mysql_repository"]

    try:
        result = await dw_mysql_repository.execute_sql(sql)

        writer({"type": "progress", "step": "执行SQL", "status": "success"})
        writer({"type": "result", "data": result})
        logger.info(f"[{trace_id}] 执行SQL结果：{result}")
        return {}

    except Exception as e:
        writer({"type": "progress", "step": "执行SQL", "status": "error"})
        writer({"type": "result", "data": [], "error": str(e)})
        logger.error(f"[{trace_id}] 执行SQL出错：{e}")
        # 不抛出异常，返回空结果
        return {}
