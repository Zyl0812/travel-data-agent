"""从 travel-data/seeds/sql/travel.sql 解析所有 CREATE TABLE，
产出 conf/meta_config.travel.yaml 骨架。

骨架已包含：
- 42 张表的 name / description（来自表 COMMENT）
- 每张表的 columns: name / role / description / alias=[] / sync
- 7 个核心业务指标（手工补全的固定段）

人工后续需补：
- 关键字段的 alias（如 "销售额" → orders.total_amount）
- 按需调整 sync=True 的字段范围
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[2]
SQL_PATH = ROOT / "travel-data" / "seeds" / "sql" / "travel.sql"
OUTPUT_PATH = ROOT / "conf" / "meta_config.travel.yaml"

# CREATE TABLE <name> ( <body> ) ENGINE=... COMMENT = '<table_comment>';
TABLE_RE = re.compile(
    r"CREATE\s+TABLE\s+`?(?P<name>\w+)`?\s*\((?P<body>.*?)\)\s*ENGINE\s*=\s*\w+"
    r"[^;]*?COMMENT\s*=\s*'(?P<comment>[^']*)'\s*;",
    re.IGNORECASE | re.DOTALL,
)
# 同上但表无 COMMENT
TABLE_RE_NO_COMMENT = re.compile(
    r"CREATE\s+TABLE\s+`?(?P<name>\w+)`?\s*\((?P<body>.*?)\)\s*ENGINE\s*=\s*\w+[^;]*?;",
    re.IGNORECASE | re.DOTALL,
)

SKIP_LINE_PREFIX = (
    "PRIMARY KEY",
    "UNIQUE KEY",
    "KEY ",
    "INDEX ",
    "CONSTRAINT",
    "FOREIGN KEY",
)

# COL_RE：行首字段名（可带反引号），后跟类型；可能带 COMMENT '<...>'
COL_RE = re.compile(
    r"^`?(?P<name>\w+)`?\s+(?P<type>[A-Z]+(?:\([^)]*\))?(?:\s+UNSIGNED)?)"
    r"[^,]*?(?:COMMENT\s+'(?P<comment>[^']*)')?\s*,?\s*$",
    re.IGNORECASE,
)


def infer_column_role(name: str, sql_type: str) -> str:
    n = name.lower()
    t = sql_type.upper()
    if n == "id" or n.endswith("_id"):
        return "id"
    if n.endswith(("_at", "_time", "_date")) or t in ("DATETIME", "DATE", "TIMESTAMP", "TIME"):
        return "time"
    if n.endswith(("_code", "_type", "_status", "_name", "_level")):
        return "dimension"
    if t.startswith(("DECIMAL", "FLOAT", "DOUBLE", "INT", "BIGINT", "TINYINT", "SMALLINT")):
        return "metric"
    return "attribute"


def infer_column_sync(name: str, comment: str) -> bool:
    """决定字段取值是否灌入 ES。
    枚举类（值少且离散）→ True；自由文本/日期/数值 → False。
    """
    n = name.lower()
    c = comment or ""
    if "枚举" in c:
        return True
    if n.endswith(("_code", "_type", "_status", "_level")):
        return True
    return False


def parse_table_body(body: str) -> list[dict[str, Any]]:
    columns: list[dict[str, Any]] = []
    for raw_line in body.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        upper = line.upper()
        if upper.startswith(SKIP_LINE_PREFIX):
            continue
        m = COL_RE.match(line)
        if not m:
            continue
        name = m.group("name")
        sql_type = m.group("type").strip()
        comment = (m.group("comment") or "").strip()
        description = comment or name
        columns.append(
            {
                "name": name,
                "role": infer_column_role(name, sql_type),
                "description": description,
                "alias": [],
                "sync": infer_column_sync(name, comment),
            }
        )
    return columns


def infer_table_role(table_name: str, columns: list[dict[str, Any]]) -> str:
    """简单启发：含订单/支付/退款/库存日历类 → fact；其他 → dimension。"""
    n = table_name.lower()
    fact_hints = (
        "orders", "order_", "payments", "refund", "_daily", "_inventory", "ledger", "_usages", "_details"
    )
    if any(h in n for h in fact_hints):
        return "fact"
    return "dimension"


def parse_sql(sql_text: str) -> list[dict[str, Any]]:
    tables: list[dict[str, Any]] = []
    seen: set[str] = set()
    for m in TABLE_RE.finditer(sql_text):
        name = m.group("name")
        seen.add(name)
        comment = m.group("comment").strip()
        body = m.group("body")
        cols = parse_table_body(body)
        tables.append(
            {
                "name": name,
                "role": infer_table_role(name, cols),
                "description": comment or name,
                "columns": cols,
            }
        )
    # 兜底：处理没有 COMMENT 的表（如有）
    for m in TABLE_RE_NO_COMMENT.finditer(sql_text):
        name = m.group("name")
        if name in seen:
            continue
        body = m.group("body")
        cols = parse_table_body(body)
        tables.append(
            {
                "name": name,
                "role": infer_table_role(name, cols),
                "description": name,
                "columns": cols,
            }
        )
    return tables


# 需求 §5 七个核心业务指标
CORE_METRICS: list[dict[str, Any]] = [
    {
        "name": "订单量",
        "description": "订单总数（订单表行数计数）",
        "relevant_columns": ["orders.id"],
        "alias": ["订单数", "下单量", "order_count"],
    },
    {
        "name": "收入金额",
        "description": "订单成交金额合计（orders.total_amount 求和）",
        "relevant_columns": ["orders.total_amount"],
        "alias": ["GMV", "营收", "销售额", "成交金额"],
    },
    {
        "name": "退款金额",
        "description": "退款打款金额合计（refund_records.amount 求和）",
        "relevant_columns": ["refund_records.amount"],
        "alias": ["退款额", "退款总额"],
    },
    {
        "name": "优惠金额",
        "description": "券核销 + 促销减免合计",
        "relevant_columns": [
            "order_coupon_usages.discount_amount",
            "order_promotion_details.discount_amount",
        ],
        "alias": ["优惠抵扣", "优惠总额"],
    },
    {
        "name": "转化率",
        "description": "已支付订单数 / 创建订单数（基于 orders.status_code 统计）",
        "relevant_columns": ["orders.status_code", "orders.id"],
        "alias": ["支付转化", "支付转化率"],
    },
    {
        "name": "退款率",
        "description": "发生退款的订单数 / 订单总数",
        "relevant_columns": ["refund_requests.id", "orders.id"],
        "alias": ["退款比例"],
    },
    {
        "name": "客单价",
        "description": "收入金额 / 订单量",
        "relevant_columns": ["orders.total_amount", "orders.id"],
        "alias": ["AOV", "平均订单金额"],
    },
]


def build_meta_config(tables: list[dict[str, Any]]) -> dict[str, Any]:
    return {"tables": tables, "metrics": CORE_METRICS}


def main() -> None:
    if not SQL_PATH.exists():
        raise FileNotFoundError(f"SQL 源文件不存在: {SQL_PATH}")
    sql_text = SQL_PATH.read_text(encoding="utf-8")
    tables = parse_sql(sql_text)
    if not tables:
        raise RuntimeError("解析未匹配到任何 CREATE TABLE，请检查正则或源文件")

    meta_config = build_meta_config(tables)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_PATH.open("w", encoding="utf-8") as f:
        yaml.dump(
            meta_config,
            f,
            allow_unicode=True,
            sort_keys=False,
            default_flow_style=False,
        )

    total_columns = sum(len(t["columns"]) for t in tables)
    sync_columns = sum(1 for t in tables for c in t["columns"] if c["sync"])
    print(f"[OK] 已生成 {OUTPUT_PATH}")
    print(f"     表数: {len(tables)} | 字段总数: {total_columns} | sync=True 字段数: {sync_columns}")
    print(f"     指标数: {len(CORE_METRICS)}")


if __name__ == "__main__":
    main()
