import json

from langchain_huggingface import HuggingFaceEmbeddings

from app.agent.context import DataAgentContext
from app.agent.graph import graph
from app.agent.state import DataAgentState
from app.api.schemas.query_schema import QueryResponse, ResultType
from app.repositories.es.value_es_repository import ValueESRepository
from app.repositories.mysql.dw.dw_mysql_repository import DWMySQLRepository
from app.repositories.mysql.meta.meta_mysql_repository import MetaMySQLRepository
from app.repositories.qdrant.column_qdrant_repository import ColumnQdrantRepository
from app.repositories.qdrant.metric_qdrant_repository import MetricQdrantRepository


class QueryService:
    def __init__(self,
                 embedding_client: HuggingFaceEmbeddings,
                 column_qdrant_repository: ColumnQdrantRepository,
                 value_es_repository: ValueESRepository,
                 metric_qdrant_repository: MetricQdrantRepository,
                 meta_mysql_repository: MetaMySQLRepository,
                 dw_mysql_repository: DWMySQLRepository):
        self.embedding_client = embedding_client
        self.column_qdrant_repository = column_qdrant_repository
        self.value_es_repository = value_es_repository
        self.metric_qdrant_repository = metric_qdrant_repository
        self.meta_mysql_repository = meta_mysql_repository
        self.dw_mysql_repository = dw_mysql_repository

    def _create_context(self) -> DataAgentContext:
        """创建上下文"""
        return DataAgentContext(
            embedding_client=self.embedding_client,
            column_qdrant_repository=self.column_qdrant_repository,
            value_es_repository=self.value_es_repository,
            metric_qdrant_repository=self.metric_qdrant_repository,
            meta_mysql_repository=self.meta_mysql_repository,
            dw_mysql_repository=self.dw_mysql_repository
        )

    async def query(self, query_str: str):
        """流式查询"""
        context = self._create_context()
        state = DataAgentState(query=query_str)
        try:
            async for chunk in graph.astream(input=state, context=context, stream_mode="custom"):
                # 查询结果是列表[字典]，需要转成json
                yield f"data: {json.dumps(chunk, ensure_ascii=False, default=str)}\n\n" # SSE格式发送数据data:...\n\n
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)}, ensure_ascii=False, default=str)}\n\n"

    async def query_json(self, query_str: str) -> QueryResponse:
        """JSON 查询 - 用于前端页面"""
        context = self._create_context()
        state = DataAgentState(query=query_str)
        
        result_data = []
        result_columns = []
        intent = "simple"
        sql = ""
        error = None
        tables = []
        metrics = []

        try:
            # 执行 graph
            final_state = await graph.ainvoke(input=state, context=context)
            
            # 提取结果
            intent = final_state.get("intent", "simple")
            sql = final_state.get("sql", "")
            error = final_state.get("error")
            
            # 提取识别的表和指标
            table_infos = final_state.get("table_infos", [])
            metric_infos = final_state.get("metric_infos", [])
            
            tables = [t.get("name", "") for t in table_infos if t.get("name")]
            metrics = [m.get("name", "") for m in metric_infos if m.get("name")]
            
            # 执行 SQL 获取数据
            if sql and not error:
                try:
                    rows = await self.dw_mysql_repository.execute_sql(sql)
                    if rows and len(rows) > 0:
                        result_columns = list(rows[0].keys())
                        result_data = rows
                except Exception as e:
                    error = str(error) if error else str(e)

        except Exception as e:
            error = str(e)

        # 确定结果类型
        result_type = ResultType.TABLE
        if intent == "trend":
            result_type = ResultType.TIME_SERIES
        elif intent == "compare":
            result_type = ResultType.COMPARISON
        elif intent == "ranking":
            result_type = ResultType.RANKING

        return QueryResponse(
            query=query_str,
            intent=intent,
            result_type=result_type,
            sql=sql,
            columns=result_columns,
            data=result_data,
            row_count=len(result_data),
            error=error,
            tables=tables,
            metrics=metrics
        )