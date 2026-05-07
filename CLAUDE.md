# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**data-agent** 是面向旅游场景的智能问数系统：用户用自然语言提问，系统输出结构化数据 / 统计结果 / 趋势对比。

业务数据来自 `travel-data/` 子项目（43 张表，覆盖维度/用户/商品/营销/交易/售后六大业务域）。

技术栈：LangGraph 编排 + 三路召回（Qdrant 向量 / ES 关键词 / MySQL 元数据）+ LLM SQL 生成 → 校验 → 纠错 → 执行。

## 当前架构

### 服务依赖
| 组件 | 用途 | 配置位置 |
|---|---|---|
| MySQL `meta` | 语义元数据（表/字段/指标/取值） | `db_meta` |
| MySQL `travel` | 业务数据（订单/商品/用户/...） | `db_dw` |
| Qdrant | 字段、指标向量召回（cosine, dim=1024） | `qdrant` |
| Elasticsearch | 字段取值的关键词召回（IK 中文分词） | `es` |
| Embedding | 本地 `bge-large-zh-v1.5`（CPU/GPU） | `embedding` |
| LLM | DeepSeek / OpenRouter 兼容接口 | `llm` |

部署：根目录 `docker-compose.yaml` 起 MySQL + Qdrant + ES 三件套；Embedding 走本地路径；LLM 走远端 API。

### 代码组织
```
app/
├── agent/                         # LangGraph 工作流
│   ├── graph.py                   # 图编排
│   ├── state.py                   # 状态定义
│   ├── context.py                 # 上下文定义
│   ├── llm.py                     # LLM 配置
│   ├── llm_utils.py               # LLM 调用工具（重试/降级）
│   └── nodes/                     # 处理节点
│       ├── extract_keywords.py    # 关键词提取 + 意图识别
│       ├── recall_column.py       # 字段召回
│       ├── recall_value.py        # 取值召回
│       ├── recall_metric.py       # 指标召回
│       ├── merge_retrieved_info.py # 合并召回信息
│       ├── filter_table.py        # 表过滤
│       ├── filter_metric.py       # 指标过滤
│       ├── add_extra_context.py   # 添加上下文（枚举值/表字段）
│       ├── generate_sql.py        # SQL 生成
│       ├── validate_sql.py        # SQL 验证
│       ├── correct_sql.py         # SQL 校正
│       ├── execute_sql.py         # SQL 执行
│       ├── trend.py               # 趋势分析增强
│       ├── compare.py             # 对比分析增强
│       ├── ranking.py             # 排名分析增强
│       └── utils.py               # 工具函数（trace_id/日志）
├── api/                           # FastAPI 入口
│   ├── routers/query_router.py    # 路由定义
│   ├── schemas/query_schema.py    # 数据模型
│   ├── templates/index.html       # 前端页面
│   └── dependencies.py            # 依赖注入
├── clients/                       # 服务客户端
│   ├── embedding_client_manager.py
│   ├── mysql_client_manager.py
│   ├── qdrant_client_manager.py
│   └── es_client_manager.py
├── conf/                          # 配置 schema
├── core/                          # 基础设施
│   ├── context.py                 # request_id 上下文
│   ├── lifespan.py                # FastAPI 生命周期
│   └── log.py                     # loguru 配置
├── entities/                      # 领域实体
├── models/                        # SQLAlchemy ORM
├── prompts/                       # Prompt 模板
├── repositories/                  # 数据访问层
│   ├── mysql/{meta,dw}/
│   ├── qdrant/
│   └── es/
├── scripts/                       # 工具脚本
│   ├── build_meta_knowledge.py    # 元数据构建
│   └── generate_meta_skeleton.py  # 元数据骨架生成
└── services/                      # 业务服务层
    ├── meta_knowledge_service.py
    └── query_service.py
```

### LangGraph 工作流
```
extract_keywords (含意图识别: simple/ranking/trend/compare)
   ├──→ recall_column   (Qdrant 字段召回)
   ├──→ recall_value    (ES 取值召回)
   └──→ recall_metric   (Qdrant 指标召回)
        └──→ merge_retrieved_info
              ├──→ filter_table
              └──→ filter_metric
                    └──→ add_extra_context (注入枚举值/表字段字典)
                          └──→ generate_sql
                                └──→ 根据意图路由:
                                      ├─ simple → validate_sql
                                      ├─ trend → enhance_trend_sql → validate_sql
                                      ├─ compare → enhance_compare_sql → validate_sql
                                      └─ ranking → enhance_ranking_sql → validate_sql
                                            └──→ validate_sql ──[err]──→ correct_sql ──┐
                                                   │                                    ↓
                                                   └────────[ok]──────────────────→ execute_sql → END
```

## Development Setup

**Python**: 3.13 / **Package Manager**: uv

```powershell
# 1. 启动依赖服务
docker compose up -d

# 2. 配置文件
cp conf/app_config.yaml.example conf/app_config.yaml
# 编辑 conf/app_config.yaml 填入数据库密码和 LLM API Key

# 3. 生成业务数据（如需要）
cd travel-data
uv run init_db.py
uv run -m generate.main --profile full
cd ..

# 4. 构建元数据 + 向量入库
uv run python -m app.scripts.build_meta_knowledge -c conf/meta_config.travel.yaml

# 5. 启动服务
uv run python -m main

# 6. 运行评测
uv run python -m test.evals.run_evals
```

## Configuration

`conf/app_config.yaml` 字段：`logging` / `db_meta` / `db_dw` / `qdrant` / `embedding` / `es` / `llm`。

新增配置段流程：
1. `app/conf/app_config.py` 增 dataclass
2. 注册到 `AppConfig`
3. `conf/app_config.yaml` 加同名键
4. 通过 `app_config.<段>` 访问

## Key Patterns

- **Async-first**：所有 IO 客户端走 async/await（asyncmy + AsyncQdrantClient + AsyncElasticsearch）
- **Repository 三层**：MySQL (元数据/业务) / Qdrant (向量) / ES (关键词) 各自封装，互不依赖
- **Manager 单例**：每个 `*ClientManager` 模块级单例 + `init()` 显式初始化，由 `core/lifespan.py` 在 FastAPI 启动时统一拉起
- **Context 注入**：LangGraph 用 `DataAgentContext` 把 repositories + embedding client 传到每个节点，节点函数纯净不持有客户端
- **Trace ID**：每条 query 生成唯一 trace_id，贯穿所有节点日志
- **容错机制**：召回失败不阻断、LLM 调用自动重试、SQL 校正有次数限制

## 后续实施计划（旅游问数闭环）

### Phase 1 — 元数据语义层对齐 ✅ 已完成
**目标**：把 43 张业务表的元数据 + 字段释义 + 取值字典 + 指标定义全量灌入 `meta` 库，并入向量/ES 索引。

**已完成**：
- ✅ `docker-compose.yaml` 三件套（MySQL + Qdrant + ES）就绪
- ✅ `conf/meta_config.travel.yaml` 骨架（43 表 / 485 字段 / 7 核心指标）
- ✅ `build_meta_knowledge.py` 自动建 meta 库 4 张表
- ✅ 修复指标定义中的字段引用（`orders.total_amount` → `orders.paid_amount`）
- ✅ 三处存储计数对齐验收通过

### Phase 2 — 召回与生成质量打磨 ✅ 已完成
**目标**：用一组旅游场景固定 case 跑 graph，把召回 / SQL 生成准确率拉上来。

**已完成**：
- ✅ 评测集 `test/evals/travel_questions.yaml`（15 题，覆盖三类场景）
- ✅ 优化 4 个 prompt 模板（增加旅游领域示例和时间口径）
- ✅ 增强 `add_extra_context` 注入枚举值字典和表字段字典
- ✅ 评测脚本 `test/evals/run_evals.py`（支持重试和报告生成）
- ✅ 修复 SQL 输出清理（移除 markdown 代码块标记）

**验收**：评测集可执行，SQL 可执行率 ≥ 60%

### Phase 3 — 复杂场景节点 ✅ 已完成
**目标**：覆盖需求 §5.3 趋势对比场景。

**已完成**：
- ✅ 在 `extract_keywords` 增加意图识别：`{simple, ranking, trend, compare}`
- ✅ 新增 `trend.py` / `compare.py` / `ranking.py` 节点
- ✅ `generate_sql.prompt` 增加时间口径规则和枚举值参考
- ✅ 结果格式 schema 扩展：`result_type` 区分表格 / 时序 / 对比 / 排名

### Phase 4 — 鲁棒性与可观测性 ✅ 已完成
**目标**：满足需求 §6 非功能要求。

**已完成**：
- ✅ Trace ID 贯穿所有节点（`app/agent/nodes/utils.py`）
- ✅ 节点执行日志（入参/出参/耗时）
- ✅ LLM 调用重试机制（`app/agent/llm_utils.py`）
- ✅ 召回失败容错（单路缺失不阻断）
- ✅ SQL 校正次数限制（最多 3 次）
- ✅ SQL 执行失败兜底

### Phase 5 — 演示闭环与交付 ✅ 已完成
**目标**：满足需求 §7 / §8 的交付与验收。

**已完成**：
- ✅ 前端页面 `app/api/templates/index.html`（Claude 风格设计）
- ✅ JSON 查询接口 `POST /api/query/json`
- ✅ 支持表格/柱状图/折线图/饼图展示
- ✅ SQL 语法高亮显示
- ✅ Pipeline 进度可视化
- ✅ README.md 部署文档

## 协作要求

- **Async first**：新增 IO 一律 async；同步代码仅限于脚本入口
- **Repository 隔离**：业务库（dw）只读；元数据库（meta）写入仅限 `meta_knowledge_service` 与 scripts
- **节点纯函数**：LangGraph 节点不持有客户端，所有依赖经 `DataAgentContext` 传入
- **Prompt 外置**：所有 LLM prompt 落 `prompts/`，不内联到节点
- **凭据外置**：YAML 中的密码 / API key 走环境变量或 secret 管理
- **修改后同步说明**：`CLAUDE.md` 与 `AGENTS.md` 内容需保持一致

## Notes

- MySQL 用 `async_sessionmaker` 管理会话；meta / dw 各自独立 sessionmaker
- Qdrant 默认 cosine 距离；embedding 维度 1024（匹配 bge-large-zh-v1.5）
- HuggingFace embeddings 当前走本地路径（`embedding.model_path`），非外部 endpoint
- Embedding 默认 CPU，如有 GPU 可安装 CUDA 版 PyTorch 加速
- `travel-data/` 是独立子工程，用于生成业务数据（可选保留）
