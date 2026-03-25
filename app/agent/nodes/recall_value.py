from langgraph.runtime import Runtime
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import JsonOutputParser

from app.core.log import logger
from app.agent.context import DataAgentContext
from app.agent.state import DataAgentState
from app.agent.llm import llm
from app.entities.value_info import ValueInfo
from app.prompt.prompt_loader import load_prompt


async def recall_value(state: DataAgentState, runtime: Runtime[DataAgentContext]):
    writer = runtime.stream_writer
    writer({"type": "progress", "step": "召回字段取值", "status": "running"})
    
    query = state['query']
    keywords = state['keywords']
    
    value_es_repository = runtime.context['value_es_repository']
    try:
        # 1. 通过大模型扩充关键词
        prompt = PromptTemplate(
            template=load_prompt('extend_keywords_for_value_recall'),
            input_variables=['query']
        )
        
        chain = prompt | llm | JsonOutputParser()
        
        result = await chain.ainvoke({'query': query})
    
        # 2. 关键词列表 已抽取的关键词＋扩充后的
        keywords = list(set(keywords + result))
    
        # 3. 遍历关键词列表，采用全文查询ES获取值信息
        retrieved_value_map:dict[str, ValueInfo] = {}
        for keyword in keywords:
            value_infos = await value_es_repository.search(keyword)
            for value_info in value_infos:
                if value_info.id not in retrieved_value_map:
                    retrieved_value_map[value_info.id] = value_info
    
        writer({"type": "progress", "step": "召回字段取值", "status": "success"})
        logger.info(f"召回字段取值成功：{list(retrieved_value_map.keys())}")
        # 4. 更新state
        return {'retrieved_value_map': retrieved_value_map}
    except Exception as e:
        logger.error(f"召回字段取值失败: {str(e)}")
        writer({"type": "progress", "step": "召回字段取值", "status": "failed"})
        raise