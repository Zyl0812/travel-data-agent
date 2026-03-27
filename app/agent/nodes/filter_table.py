import yaml

from langchain_core.prompts import PromptTemplate
from langgraph.runtime import Runtime
from langchain_core.output_parsers import JsonOutputParser

from app.core.log import logger
from app.agent.context import DataAgentContext
from app.agent.llm import llm
from app.agent.state import DataAgentState
from app.prompt.prompt_loader import load_prompt


async def filter_table(state: DataAgentState, runtime: Runtime[DataAgentContext]):
    writer = runtime.stream_writer
    writer({"type": "progress", "step": "过滤表格", "status": "running"})
    
    # 1. 得到已召回的表格信息
    table_infos = state.get("table_infos", [])
    query = state.get("query", "")
    
    try:
        # 2. 调用 LLM 返回回答问题需要用到的表格
        prompt = PromptTemplate(
            template=load_prompt('filter_table_info'),
            input_variables=['query', 'table_infos'],
        )
        output_parser = JsonOutputParser()
        chain = prompt | llm | output_parser
        
        result = await chain.ainvoke({
            'query': query,
            'table_infos': yaml.dump(table_infos, allow_unicode=True, sort_keys=False)
        })
        
        # 3. 构建新列表，只保留需要的表格及其字段
        filtered_table_infos = [
            {**table_info, 'columns': [column for column in table_info['columns'] if column['name'] in result[table_info['name']]]}
            for table_info in table_infos
            if table_info['name'] in result
        ]

        writer({"type": "progress", "step": "过滤表格", "status": "success"})
        logger.info(f'过滤表格成功: {[table_info["name"] for table_info in filtered_table_infos]}')
        logger.info(f'过滤字段成功: {[column["name"] for table_info in filtered_table_infos for column in table_info["columns"]]}')

        # 4. 封装 state 更新表格信息
        return {'table_infos': filtered_table_infos}
    
    except Exception as e:
        writer({"type": "progress", "step": "过滤表格", "status": "error"})
        logger.error(f'过滤表格失败: {e}')
        raise
