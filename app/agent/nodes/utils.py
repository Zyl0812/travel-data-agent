"""节点执行追踪工具：提供 trace_id 和节点执行日志"""

import time
import uuid
from functools import wraps
from typing import Any, Callable

from app.core.log import logger


def generate_trace_id() -> str:
    """生成追踪ID"""
    return str(uuid.uuid4())[:8]


def log_node_execution(node_name: str) -> Callable:
    """装饰器：记录节点执行日志（入参、出参、耗时）"""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(state: dict, runtime: Any) -> dict:
            start_time = time.time()
            trace_id = state.get("trace_id", "unknown")
            
            # 记录入参（只记录关键字段，避免日志过大）
            log_input = {k: v for k, v in state.items() 
                        if k in ["query", "intent", "keywords", "error"]}
            logger.info(f"[{trace_id}] {node_name} 开始执行，入参: {log_input}")
            
            try:
                result = await func(state, runtime)
                elapsed = time.time() - start_time
                
                # 记录出参
                log_output = {k: v for k, v in result.items() 
                            if k not in ["table_infos", "metric_infos", "retrieved_columns", "retrieved_values", "retrieved_metrics"]}
                logger.info(f"[{trace_id}] {node_name} 执行成功，耗时: {elapsed:.2f}s，出参: {log_output}")
                
                return result
                
            except Exception as e:
                elapsed = time.time() - start_time
                logger.error(f"[{trace_id}] {node_name} 执行失败，耗时: {elapsed:.2f}s，错误: {str(e)}")
                raise
        
        return wrapper
    return decorator


def safe_execute(func: Callable, default_value: Any = None, error_msg: str = "") -> Any:
    """安全执行函数，捕获异常并返回默认值"""
    try:
        return func()
    except Exception as e:
        if error_msg:
            logger.warning(f"{error_msg}: {str(e)}")
        return default_value
