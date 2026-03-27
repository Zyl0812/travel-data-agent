from langgraph.runtime import Runtime
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import JsonOutputParser

from app.core.log import logger
from app.agent.context import DataAgentContext
from app.agent.state import DataAgentState
from app.agent.llm import llm
from app.entities.metric_info import MetricInfo
from app.prompt.prompt_loader import load_prompt


async def recall_metric(state: DataAgentState, runtime: Runtime[DataAgentContext]):
    writer = runtime.stream_writer
    writer({"type": "progress", "step": "召回指标", "status": "running"})
    
    query = state['query']
    keywords = state['keywords']
    
    embedding_client = runtime.context['embedding_client']
    metric_qdrant_repository = runtime.context['metric_qdrant_repository']
    try:
        # 1. 通过llm对指标名称扩充，为了得到回答问题需要哪些指标
        prompt = PromptTemplate(
            template=load_prompt('extend_keywords_for_metric_recall'),
            input_variables=['query']
        )
        output_parser = JsonOutputParser()
        
        chain = prompt | llm | output_parser
        
        result = await chain.ainvoke({'query': query})
        logger.info(f"扩展关键词成功: {result}")
    
        # 2. 遍历指标列表（已抽取的指标和扩充后的）查询qdrant指标向量集合
        keywords = list(set(keywords + result))
        retrieved_metric_map:dict[str, MetricInfo] = {}
        
        for keyword in keywords:
            embedding = await embedding_client.aembed_query(keyword)
            metric_infos:list[MetricInfo] = await metric_qdrant_repository.search(embedding)
            # 相同字段去重
            for metric_info in metric_infos:
                metric_id = metric_info.id
                if metric_id not in retrieved_metric_map:
                    retrieved_metric_map[metric_id] = metric_info
        
        writer({"type": "progress", "step": "召回指标", "status": "success"})
        logger.info(f"召回指标成功: {retrieved_metric_map.keys()} ")
        # 3. 将结果写入state
        return {"retrieved_metrics": list(retrieved_metric_map.values())}
    
    except Exception as e:
        writer({"type": "progress", "step": "召回指标", "status": "error"})
        logger.error(f"召回字段失败: {str(e)}")
        raise