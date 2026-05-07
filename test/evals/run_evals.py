"""Phase 2 评测脚本：验证召回和SQL生成准确率"""

import asyncio
import yaml
from pathlib import Path
from datetime import datetime
import time

from app.agent.graph import graph
from app.agent.context import DataAgentContext
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
from app.core.log import logger


class EvalResult:
    """评测结果"""
    def __init__(self, eval_id: int, category: str, question: str):
        self.eval_id = eval_id
        self.category = category
        self.question = question
        self.retrieved_tables: list[str] = []
        self.retrieved_columns: list[str] = []
        self.generated_sql: str = ""
        self.sql_executable: bool = False
        self.execution_result: list = []
        self.error: str = ""
        self.table_recall_hit: bool = False
        self.column_recall_hit: bool = False

    def to_dict(self) -> dict:
        return {
            "eval_id": self.eval_id,
            "category": self.category,
            "question": self.question,
            "retrieved_tables": self.retrieved_tables,
            "retrieved_columns": self.retrieved_columns,
            "generated_sql": self.generated_sql,
            "sql_executable": self.sql_executable,
            "execution_result_count": len(self.execution_result),
            "error": self.error,
            "table_recall_hit": self.table_recall_hit,
            "column_recall_hit": self.column_recall_hit,
        }


async def run_single_eval(eval_case: dict, context: DataAgentContext, max_retries: int = 3) -> EvalResult:
    """运行单个评测用例"""
    result = EvalResult(
        eval_id=eval_case["id"],
        category=eval_case["category"],
        question=eval_case["question"],
    )

    for attempt in range(max_retries):
        try:
            # 调用 graph
            state = DataAgentState(query=eval_case["question"])

            # 使用 ainvoke 获取完整状态
            final_state = await graph.ainvoke(input=state, context=context)

            # 提取召回的表和字段
            if "table_infos" in final_state:
                for table_info in final_state["table_infos"]:
                    result.retrieved_tables.append(table_info["name"])
                    for col in table_info.get("columns", []):
                        result.retrieved_columns.append(f"{table_info['name']}.{col['name']}")

            # 提取生成的 SQL
            if "sql" in final_state:
                result.generated_sql = final_state["sql"]

            # 提取错误信息
            if "error" in final_state and final_state["error"]:
                result.error = final_state["error"]

            # 验证表召回
            expected_tables = set(eval_case.get("expected_tables", []))
            retrieved_tables = set(result.retrieved_tables)
            if expected_tables:
                result.table_recall_hit = expected_tables.issubset(retrieved_tables)

            # 验证字段召回
            expected_columns = set(eval_case.get("expected_columns", []))
            retrieved_columns = set(result.retrieved_columns)
            if expected_columns:
                # 检查期望的字段是否在召回的字段中（部分匹配）
                for expected_col in expected_columns:
                    if any(expected_col in retrieved_col for retrieved_col in retrieved_columns):
                        result.column_recall_hit = True
                        break

            # 验证 SQL 可执行性
            if result.generated_sql and not result.error:
                result.sql_executable = True

            # 成功则跳出重试循环
            break

        except Exception as e:
            error_msg = str(e)
            if "429" in error_msg and attempt < max_retries - 1:
                # 限流错误，等待后重试
                wait_time = (attempt + 1) * 10  # 递增等待时间
                logger.warning(f"[Eval {result.eval_id}] 限流错误，等待 {wait_time} 秒后重试 (尝试 {attempt + 1}/{max_retries})")
                time.sleep(wait_time)
            else:
                result.error = error_msg
                logger.error(f"[Eval {result.eval_id}] 执行失败: {e}")
                break

    return result


async def run_evals():
    """运行所有评测用例"""
    # 1. 加载评测集
    eval_file = Path(__file__).parent / "travel_questions.yaml"
    with open(eval_file, "r", encoding="utf-8") as f:
        eval_data = yaml.safe_load(f)

    eval_cases = eval_data["evals"]
    logger.info(f"加载评测集完成，共 {len(eval_cases)} 题")

    # 2. 初始化客户端
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

    # 3. 创建 context
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

        # 4. 运行评测
        results: list[EvalResult] = []
        for i, eval_case in enumerate(eval_cases):
            logger.info(f"开始评测 [{eval_case['id']}] {eval_case['question']}")
            result = await run_single_eval(eval_case, context)
            results.append(result)
            logger.info(f"评测完成 [{eval_case['id']}] 表召回命中: {result.table_recall_hit}, SQL可执行: {result.sql_executable}")
            
            # 每题之间等待，避免限流
            if i < len(eval_cases) - 1:
                wait_seconds = 5
                logger.info(f"等待 {wait_seconds} 秒后继续下一题...")
                time.sleep(wait_seconds)

    # 5. 生成评测报告
    generate_report(results, eval_cases)

    # 6. 关闭客户端
    await qdrant_client_manager.close()
    await es_client_manager.close()
    await meta_mysql_client_manager.close()
    await dw_mysql_client_manager.close()


def generate_report(results: list[EvalResult], eval_cases: list[dict]):
    """生成评测报告"""
    report_dir = Path(__file__).parent / "reports"
    report_dir.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_file = report_dir / f"eval_report_{timestamp}.md"

    # 统计
    total = len(results)
    table_recall_hits = sum(1 for r in results if r.table_recall_hit)
    column_recall_hits = sum(1 for r in results if r.column_recall_hit)
    sql_executable_count = sum(1 for r in results if r.sql_executable)
    error_count = sum(1 for r in results if r.error)

    # 按类别统计
    category_stats = {}
    for result in results:
        cat = result.category
        if cat not in category_stats:
            category_stats[cat] = {"total": 0, "table_hit": 0, "sql_ok": 0}
        category_stats[cat]["total"] += 1
        if result.table_recall_hit:
            category_stats[cat]["table_hit"] += 1
        if result.sql_executable:
            category_stats[cat]["sql_ok"] += 1

    # 生成报告
    report = f"""# Phase 2 评测报告

**评测时间**: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
**评测题目数**: {total}

## 总体统计

| 指标 | 数量 | 比例 |
|------|------|------|
| 表召回命中 | {table_recall_hits}/{total} | {table_recall_hits/total*100:.1f}% |
| 字段召回命中 | {column_recall_hits}/{total} | {column_recall_hits/total*100:.1f}% |
| SQL可执行 | {sql_executable_count}/{total} | {sql_executable_count/total*100:.1f}% |
| 执行错误 | {error_count}/{total} | {error_count/total*100:.1f}% |

## 分类别统计

| 类别 | 题目数 | 表召回命中 | SQL可执行 |
|------|--------|------------|-----------|
"""
    for cat, stats in category_stats.items():
        report += f"| {cat} | {stats['total']} | {stats['table_hit']}/{stats['total']} | {stats['sql_ok']}/{stats['total']} |\n"

    report += """
## 详细结果

| ID | 类别 | 问题 | 表召回 | SQL可执行 | 错误 |
|----|------|------|--------|-----------|------|
"""
    for result in results:
        table_status = "✅" if result.table_recall_hit else "❌"
        sql_status = "✅" if result.sql_executable else "❌"
        error_msg = result.error[:50] + "..." if len(result.error) > 50 else result.error
        report += f"| {result.eval_id} | {result.category} | {result.question} | {table_status} | {sql_status} | {error_msg} |\n"

    report += """
## 错误归因

"""
    for result in results:
        if result.error:
            report += f"### 评测 {result.eval_id}: {result.question}\n"
            report += f"- **错误**: {result.error}\n"
            if not result.table_recall_hit:
                report += "- **归因**: 召回缺失（期望的表未被召回）\n"
            elif not result.sql_executable:
                report += "- **归因**: SQL生成错误\n"
            else:
                report += "- **归因**: 其他原因\n"
            report += "\n"

    # 写入文件
    with open(report_file, "w", encoding="utf-8") as f:
        f.write(report)

    logger.info(f"评测报告已生成: {report_file}")

    # 打印摘要
    print("\n" + "="*60)
    print("Phase 2 评测完成")
    print("="*60)
    print(f"表召回准确率: {table_recall_hits/total*100:.1f}%")
    print(f"SQL可执行率: {sql_executable_count/total*100:.1f}%")
    print(f"详细报告: {report_file}")
    print("="*60)


if __name__ == "__main__":
    asyncio.run(run_evals())
