"""Phase 1 验收脚本：核对 meta 库 / Qdrant / ES 三处计数一致性。

运行：uv run python -m test.test_meta_acceptance
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import yaml
from sqlalchemy import text

from app.clients.es_client_manager import es_client_manager
from app.clients.mysql_client_manager import meta_mysql_client_manager
from app.clients.qdrant_client_manager import qdrant_client_manager
from app.repositories.es.value_es_repository import ValueESRepository
from app.repositories.qdrant.column_qdrant_repository import ColumnQdrantRepository
from app.repositories.qdrant.metric_qdrant_repository import MetricQdrantRepository

ROOT = Path(__file__).resolve().parents[1]
META_CONFIG_PATH = ROOT / "conf" / "meta_config.travel.yaml"


def _load_expected() -> dict:
    """从 meta_config.travel.yaml 推算应当达到的计数。"""
    with META_CONFIG_PATH.open(encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    tables = cfg["tables"]
    metrics = cfg["metrics"]
    column_metric_rows = sum(len(m["relevant_columns"]) for m in metrics)
    return {
        "table_count": len(tables),
        "column_count": sum(len(t["columns"]) for t in tables),
        "metric_count": len(metrics),
        "column_metric_count": column_metric_rows,
    }


async def _check_meta_db(expected: dict, failures: list[str]) -> None:
    if meta_mysql_client_manager.session_factory is None:
        failures.append("meta_mysql session_factory 未初始化")
        return
    async with meta_mysql_client_manager.session_factory() as session:
        for table, expected_count_key, comparator in [
            ("table_info", "table_count", "eq"),
            ("column_info", "column_count", "eq"),
            ("metric_info", "metric_count", "eq"),
            ("column_metric", "column_metric_count", "eq"),
        ]:
            result = await session.execute(text(f"SELECT COUNT(*) FROM {table}"))
            actual = result.scalar_one()
            expected_val = expected[expected_count_key]
            if comparator == "eq" and actual != expected_val:
                failures.append(
                    f"meta.{table}: actual={actual}, expected={expected_val}"
                )
            else:
                print(f"  [OK] meta.{table} = {actual}")


async def _check_qdrant(expected: dict, failures: list[str]) -> None:
    if qdrant_client_manager.client is None:
        failures.append("qdrant client 未初始化")
        return
    client = qdrant_client_manager.client

    column_collection = ColumnQdrantRepository.collection_name
    metric_collection = MetricQdrantRepository.collection_name

    if not await client.collection_exists(column_collection):
        failures.append(f"Qdrant collection 缺失: {column_collection}")
    else:
        cnt = (await client.count(column_collection)).count
        # 每个字段至少产出 name + description 两个向量点（无别名时）
        if cnt < expected["column_count"] * 2:
            failures.append(
                f"Qdrant {column_collection} 点数过少: {cnt} < {expected['column_count']} * 2"
            )
        else:
            print(f"  [OK] qdrant {column_collection} points = {cnt}")

    if not await client.collection_exists(metric_collection):
        failures.append(f"Qdrant collection 缺失: {metric_collection}")
    else:
        cnt = (await client.count(metric_collection)).count
        if cnt < expected["metric_count"] * 2:
            failures.append(
                f"Qdrant {metric_collection} 点数过少: {cnt} < {expected['metric_count']} * 2"
            )
        else:
            print(f"  [OK] qdrant {metric_collection} points = {cnt}")


async def _check_es(failures: list[str]) -> None:
    if es_client_manager.client is None:
        failures.append("es client 未初始化")
        return
    client = es_client_manager.client
    index = ValueESRepository.index_name
    if not await client.indices.exists(index=index):
        failures.append(f"ES index 缺失: {index}")
        return
    result = await client.count(index=index)
    cnt = result["count"]
    if cnt <= 0:
        failures.append(f"ES index {index} 文档数为 0")
    else:
        print(f"  [OK] es {index} docs = {cnt}")


async def main() -> int:
    expected = _load_expected()
    print(f"期望计数: {expected}")

    meta_mysql_client_manager.init()
    qdrant_client_manager.init()
    es_client_manager.init()

    failures: list[str] = []
    try:
        await _check_meta_db(expected, failures)
        await _check_qdrant(expected, failures)
        await _check_es(failures)
    finally:
        await meta_mysql_client_manager.close()
        await qdrant_client_manager.close()
        await es_client_manager.close()

    if failures:
        print("\n[FAIL] 验收未通过：")
        for msg in failures:
            print(f"  - {msg}")
        return 1
    print("\n[PASS] Phase 1 验收通过")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
