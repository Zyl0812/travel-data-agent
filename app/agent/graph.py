import asyncio

from app.agent.nodes.correct_sql import correct_sql
from app.agent.nodes.execute_sql import execute_sql
from app.agent.nodes.generate_sql import generate_sql
from app.agent.nodes.validate_sql import validate_sql
from app.agent.nodes.trend import enhance_trend_sql
from app.agent.nodes.compare import enhance_compare_sql
from app.agent.nodes.ranking import enhance_ranking_sql
from langgraph.constants import END, START
from langgraph.graph import StateGraph

from app.agent.context import DataAgentContext
from app.agent.nodes.add_extra_context import add_extra_context
from app.agent.nodes.extract_keywords import extract_keywords
from app.agent.nodes.filter_metric import filter_metric
from app.agent.nodes.filter_table import filter_table
from app.agent.nodes.merge_retrieved_info import merge_retrieved_info
from app.agent.nodes.recall_column import recall_column
from app.agent.nodes.recall_metric import recall_metric
from app.agent.nodes.recall_value import recall_value
from app.agent.state import DataAgentState
from app.clients.embedding_client_manager import embedding_client_manager
from app.clients.es_client_manager import es_client_manager
from app.clients.mysql_client_manager import (
    dw_mysql_client_manager,
    meta_mysql_client_manager,
)
from app.clients.qdrant_client_manager import qdrant_client_manager
from app.repositories.es.value_es_repository import ValueESRepository
from app.repositories.mysql.dw.dw_mysql_repository import DWMySQLRepository
from app.repositories.mysql.meta.meta_mysql_repository import MetaMySQLRepository
from app.repositories.qdrant.column_qdrant_repository import ColumnQdrantRepository
from app.repositories.qdrant.metric_qdrant_repository import MetricQdrantRepository

graph_builder = StateGraph(state_schema=DataAgentState, context_schema=DataAgentContext)

# 添加节点
graph_builder.add_node("extract_keywords", extract_keywords)
graph_builder.add_node("recall_column", recall_column)
graph_builder.add_node("recall_value", recall_value)
graph_builder.add_node("recall_metric", recall_metric)
graph_builder.add_node("merge_retrieved_info", merge_retrieved_info)
graph_builder.add_node("filter_metric", filter_metric)
graph_builder.add_node("filter_table", filter_table)
graph_builder.add_node("add_extra_context", add_extra_context)
graph_builder.add_node("generate_sql", generate_sql)
graph_builder.add_node("enhance_trend_sql", enhance_trend_sql)
graph_builder.add_node("enhance_compare_sql", enhance_compare_sql)
graph_builder.add_node("enhance_ranking_sql", enhance_ranking_sql)
graph_builder.add_node("validate_sql", validate_sql)
graph_builder.add_node("correct_sql", correct_sql)
graph_builder.add_node("execute_sql", execute_sql)

# 添加关系
graph_builder.add_edge(START, "extract_keywords")
graph_builder.add_edge("extract_keywords", "recall_column")
graph_builder.add_edge("extract_keywords", "recall_value")
graph_builder.add_edge("extract_keywords", "recall_metric")
graph_builder.add_edge("recall_column", "merge_retrieved_info")
graph_builder.add_edge("recall_value", "merge_retrieved_info")
graph_builder.add_edge("recall_metric", "merge_retrieved_info")
graph_builder.add_edge("merge_retrieved_info", "filter_table")
graph_builder.add_edge("merge_retrieved_info", "filter_metric")
graph_builder.add_edge("filter_table", "add_extra_context")
graph_builder.add_edge("filter_metric", "add_extra_context")
graph_builder.add_edge("add_extra_context", "generate_sql")

# 根据意图选择不同的SQL增强节点
def route_by_intent(state: DataAgentState) -> str:
    """根据意图路由到不同的SQL增强节点"""
    intent = state.get("intent", "simple")
    if intent == "trend":
        return "enhance_trend_sql"
    elif intent == "compare":
        return "enhance_compare_sql"
    elif intent == "ranking":
        return "enhance_ranking_sql"
    else:
        return "validate_sql"  # simple 直接跳到验证

graph_builder.add_conditional_edges(
    "generate_sql",
    route_by_intent,
    {
        "enhance_trend_sql": "enhance_trend_sql",
        "enhance_compare_sql": "enhance_compare_sql",
        "enhance_ranking_sql": "enhance_ranking_sql",
        "validate_sql": "validate_sql",
    },
)

# 所有增强节点都连接到验证
graph_builder.add_edge("enhance_trend_sql", "validate_sql")
graph_builder.add_edge("enhance_compare_sql", "validate_sql")
graph_builder.add_edge("enhance_ranking_sql", "validate_sql")

def route_after_validation(state: DataAgentState) -> str:
    """验证后路由：决定是执行SQL还是校正SQL"""
    error = state.get("error")
    correction_count = state.get("sql_correction_count", 0)
    
    # 没有错误，直接执行
    if error is None or error == "":
        return "execute_sql"
    
    # 校正次数超过限制，直接执行（会返回错误）
    if correction_count >= 3:
        return "execute_sql"
    
    # 有错误且未超过校正次数，进行校正
    return "correct_sql"

graph_builder.add_conditional_edges(
    "validate_sql",
    route_after_validation,
    {"execute_sql": "execute_sql", "correct_sql": "correct_sql"},
)

graph_builder.add_edge("correct_sql", "validate_sql")  # 校正后重新验证
graph_builder.add_edge("execute_sql", END)

graph = graph_builder.compile()


if __name__ == "__main__":
    async def test_graph():
        
        meta_mysql_client_manager.init()
        dw_mysql_client_manager.init()
        embedding_client_manager.init()
        qdrant_client_manager.init()
        es_client_manager.init()
        
        assert embedding_client_manager.client is not None
        assert qdrant_client_manager.client is not None
        assert es_client_manager.client is not None
        assert meta_mysql_client_manager.session_factory is not None
        assert dw_mysql_client_manager.session_factory is not None

        async with (
            meta_mysql_client_manager.session_factory() as meta_session,
            dw_mysql_client_manager.session_factory() as dw_session,
        ):
            context = DataAgentContext(
                embedding_client=embedding_client_manager.client,
                column_qdrant_repository=ColumnQdrantRepository(qdrant_client_manager.client),
                metric_qdrant_repository=MetricQdrantRepository(qdrant_client_manager.client),
                value_es_repository=ValueESRepository(es_client_manager.client),
                meta_mysql_repository=MetaMySQLRepository(meta_session),
                dw_mysql_repository=DWMySQLRepository(dw_session),
            )

            async for chunk in graph.astream(input=DataAgentState(query="统计华北地区卖了多少钱"), context=context, stream_mode="custom"):
                print(chunk)
        
        await qdrant_client_manager.close()
        await es_client_manager.close()
        await meta_mysql_client_manager.close()
        await dw_mysql_client_manager.close()
        
    asyncio.run(test_graph())