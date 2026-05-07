"""LLM 调用工具：提供重试和降级机制"""

import asyncio
from typing import Any, Optional

from langchain_core.language_models import BaseChatModel
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate

from app.core.log import logger


async def invoke_with_retry(
    chain: Any,
    input_data: dict,
    max_retries: int = 3,
    retry_delay: float = 1.0,
    fallback_value: Any = None,
    trace_id: str = "unknown"
) -> Any:
    """带重试机制的 LLM 调用
    
    Args:
        chain: LLM chain
        input_data: 输入数据
        max_retries: 最大重试次数
        retry_delay: 重试延迟（秒）
        fallback_value: 重试失败后的降级值
        trace_id: 追踪ID
    
    Returns:
        LLM 调用结果或降级值
    """
    last_error = None
    
    for attempt in range(max_retries):
        try:
            result = await chain.ainvoke(input_data)
            return result
        except Exception as e:
            last_error = e
            error_msg = str(e)
            
            # 检查是否是限流错误
            if "429" in error_msg or "rate" in error_msg.lower():
                wait_time = retry_delay * (attempt + 1)  # 递增等待时间
                logger.warning(f"[{trace_id}] LLM 调用被限流，等待 {wait_time}s 后重试 (尝试 {attempt + 1}/{max_retries})")
                await asyncio.sleep(wait_time)
            elif attempt < max_retries - 1:
                logger.warning(f"[{trace_id}] LLM 调用失败，{retry_delay}s 后重试 (尝试 {attempt + 1}/{max_retries}): {error_msg}")
                await asyncio.sleep(retry_delay)
            else:
                logger.error(f"[{trace_id}] LLM 调用失败，已达最大重试次数: {error_msg}")
    
    # 所有重试都失败，返回降级值
    if fallback_value is not None:
        logger.warning(f"[{trace_id}] 使用降级值: {fallback_value}")
        return fallback_value
    
    # 没有降级值，抛出最后一个错误
    raise last_error


async def safe_llm_call(
    prompt_template: str,
    input_variables: list[str],
    input_data: dict,
    llm: BaseChatModel,
    max_retries: int = 3,
    fallback_value: Any = None,
    trace_id: str = "unknown"
) -> str:
    """安全的 LLM 调用，包含重试和降级
    
    Args:
        prompt_template: prompt 模板
        input_variables: 输入变量列表
        input_data: 输入数据
        llm: LLM 模型
        max_retries: 最大重试次数
        fallback_value: 降级值
        trace_id: 追踪ID
    
    Returns:
        LLM 输出字符串或降级值
    """
    try:
        prompt = PromptTemplate(
            template=prompt_template,
            input_variables=input_variables,
        )
        output_parser = StrOutputParser()
        chain = prompt | llm | output_parser
        
        return await invoke_with_retry(
            chain=chain,
            input_data=input_data,
            max_retries=max_retries,
            fallback_value=fallback_value,
            trace_id=trace_id
        )
    except Exception as e:
        logger.error(f"[{trace_id}] safe_llm_call 失败: {str(e)}")
        if fallback_value is not None:
            return fallback_value
        raise
