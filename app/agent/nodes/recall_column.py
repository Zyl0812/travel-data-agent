from langgraph.runtime import Runtime
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import JsonOutputParser

from app.core.log import logger
from app.agent.context import DataAgentContext
from app.agent.state import DataAgentState
from app.agent.llm import llm
from app.agent.nodes.utils import log_node_execution
from app.entities.column_info import ColumnInfo
from app.prompt.prompt_loader import load_prompt


@log_node_execution("recall_column")
async def recall_column(state: DataAgentState, runtime: Runtime[DataAgentContext]):
    writer = runtime.stream_writer
    writer({"type": "progress", "step": "召回字段", "status": "running"})
    
    trace_id = state.get("trace_id", "unknown")
    query = state['query']
    keywords = state['keywords']
    
    embedding_client = runtime.context['embedding_client']
    column_qdrant_repository = runtime.context['column_qdrant_repository']
    
    try:
        # 1. 调用大模型对原query进行增强扩展关键词
        prompt = PromptTemplate(
            template=load_prompt('extend_keywords_for_column_recall'),
            input_variables=['query']
        )
        output_parser = JsonOutputParser()
        
        chain = prompt | llm | output_parser
        
        try:
            result = await chain.ainvoke({'query': query})
            logger.info(f"[{trace_id}] 扩展关键词成功: {result}")
        except Exception as e:
            logger.warning(f"[{trace_id}] 扩展关键词失败，使用原始关键词: {str(e)}")
            result = []
        
        # 2. 遍历抽取出来的关键词加拓展后的关键词列表查询qdrant进行语义相近检索
        keywords = list(set(keywords + result))
        
        retrieved_columns_map:dict[str, ColumnInfo] = {}
        
        for keyword in keywords:
            try:
                embedding = await embedding_client.aembed_query(keyword)
                column_infos:list[ColumnInfo] = await column_qdrant_repository.search(embedding)
                # 相同字段去重
                for column_info in column_infos:
                    column_id = column_info.id
                    if column_id not in retrieved_columns_map:
                        retrieved_columns_map[column_id] = column_info
            except Exception as e:
                logger.warning(f"[{trace_id}] 关键词 '{keyword}' 召回失败: {str(e)}")
                continue
        
        writer({"type": "progress", "step": "召回字段", "status": "success"})
        logger.info(f"[{trace_id}] 召回字段成功: {retrieved_columns_map.keys()} ")
        # 3. 将结果写入state
        return {"retrieved_columns": list(retrieved_columns_map.values())}
        
    except Exception as e:
        writer({"type": "progress", "step": "召回字段", "status": "error"})
        logger.error(f"[{trace_id}] 召回字段失败: {str(e)}")
        # 返回空列表，不阻断流程
        return {"retrieved_columns": []}