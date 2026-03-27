import yaml

from langchain_core.prompts import PromptTemplate
from langgraph.runtime import Runtime
from langchain_core.output_parsers import JsonOutputParser

from app.core.log import logger
from app.agent.context import DataAgentContext
from app.agent.llm import llm
from app.agent.state import DataAgentState
from app.prompt.prompt_loader import load_prompt


async def filter_metric(state: DataAgentState, runtime: Runtime[DataAgentContext]):
    writer = runtime.stream_writer
    writer({"type": "progress", "step": "过滤指标", "status": "running"})
    
    # 1. 得到已召回的指标
    metric_infos = state.get("metric_infos", [])
    query = state.get("query", "")
    
    try:
        # 2. 调用 LLM 返回回答问题需要用到的指标
        prompt = PromptTemplate(
            template=load_prompt('filter_metric_info'),
            input_variables=['query', 'metric_infos'],
        )
        output_parser = JsonOutputParser()
        chain = prompt | llm | output_parser
        
        result = await chain.ainvoke({
            'query': query,
            'metric_infos': yaml.dump(metric_infos, allow_unicode=True, sort_keys=False)
        })
        
        # 3. 构建新列表，只保留需要的指标
        filtered_metric_infos = [metric_info for metric_info in metric_infos if metric_info['name'] in result]

        writer({"type": "progress", "step": "过滤指标", "status": "success"})
        logger.info(f'过滤指标成功: {[metric_info["name"] for metric_info in filtered_metric_infos]}')

        # 4. 封装 state 更新指标信息
        return {'metric_infos': filtered_metric_infos}
    
    except Exception as e:
        writer({"type": "progress", "step": "过滤指标", "status": "error"})
        logger.error(f'过滤指标失败: {e}')
        raise