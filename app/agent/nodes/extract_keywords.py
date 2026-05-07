import jieba.analyse
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate
from langgraph.runtime import Runtime

from app.agent.context import DataAgentContext
from app.agent.llm import llm
from app.agent.state import DataAgentState
from app.agent.nodes.utils import generate_trace_id, log_node_execution
from app.core.log import logger
from app.core.context import request_id_ctx_var
from app.prompt.prompt_loader import load_prompt


@log_node_execution("extract_keywords")
async def extract_keywords(state: DataAgentState, runtime: Runtime[DataAgentContext]):

    writer = runtime.stream_writer
    writer({"type": "progress", "step": "提取关键字", "status": "running"})

    try:
        # 0. 生成 trace_id 并注入到上下文
        trace_id = generate_trace_id()
        request_id_ctx_var.set(trace_id)

        # 1. 获取用户问题
        query = state.get("query")

        # 2. 使用jieba对关键词进行分词，得到关键词列表
        # 对查询进行分词，只提取指定词性的词
        allow_pos = (
            "n",  # 名词: 数据、服务器、表格
            "nr",  # 人名: 张三、李四
            "ns",  # 地名: 北京、上海
            "nt",  # 机构团体名: 政府、学校、某公司
            "nz",  # 其他专有名词: Unicode、哈希算法、诺贝尔奖
            "v",  # 动词: 运行、开发
            "vn",  # 名动词: 工作、研究
            "a",  # 形容词: 美丽、快速
            "an",  # 名形词: 难度、合法性、复杂度
            "eng",  # 英文
            "i",  # 成语
            "l",  # 常用固定短语
        )
        keywords = jieba.analyse.extract_tags(query, allowPOS=allow_pos)
        keywords = list(set(keywords + [query]))

        # 3. 使用 LLM 识别用户意图
        intent = await _extract_intent(query)

        writer({"type": "progress", "step": "提取关键字", "status": "success"})
        logger.info(f"[{trace_id}] 提取关键字成功: {keywords}, 意图: {intent}")
        # 4. 返回结果
        return {"trace_id": trace_id, "keywords": keywords, "intent": intent}

    except Exception as e:
        writer({"type": "progress", "step": "提取关键字", "status": "error"})
        logger.error(f"提取关键字失败: {str(e)}")
        raise


async def _extract_intent(query: str) -> str:
    """使用 LLM 提取用户意图"""
    try:
        prompt = PromptTemplate(
            template=load_prompt("extract_intent"),
            input_variables=["query"],
        )
        output_parser = StrOutputParser()
        chain = prompt | llm | output_parser

        intent = await chain.ainvoke({"query": query})
        intent = intent.strip().lower()

        # 验证意图是否有效
        valid_intents = ["simple", "ranking", "trend", "compare"]
        if intent not in valid_intents:
            intent = "simple"  # 默认为简单查询

        return intent
    except Exception as e:
        logger.error(f"意图识别失败: {str(e)}")
        return "simple"  # 出错时默认为简单查询
