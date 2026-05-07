# Travel Data Agent - 旅游问数系统

一个面向旅游场景的智能问数系统：用户用自然语言提问，系统输出结构化数据 / 统计结果 / 趋势对比。

## 功能特性

- **自然语言查询**：用户可以直接用中文提问，无需编写 SQL
- **三路召回**：Qdrant 向量检索 + ES 关键词检索 + MySQL 元数据检索
- **智能 SQL 生成**：基于 LLM 自动生成 SQL 并执行
- **多种分析场景**：支持简单查询、排名分析、趋势分析、对比分析
- **可视化展示**：支持表格、柱状图、折线图、饼图等多种展示方式
- **Pipeline 可视化**：实时展示查询处理流程
- **SQL 语法高亮**：生成的 SQL 语法高亮显示

## 技术栈

- **后端**：FastAPI + LangGraph + SQLAlchemy
- **数据库**：MySQL 8.0 + Qdrant + Elasticsearch（IK 中文分词）
- **LLM**：DeepSeek / OpenRouter 兼容接口
- **Embedding**：BGE-Large-ZH-v1.5（支持 CPU/GPU）
- **前端**：原生 HTML + CSS + JavaScript + Chart.js
- **包管理**：uv（Python 3.13+）

## 快速开始

### 1. 环境准备

```bash
# 克隆仓库
git clone https://github.com/Zyl0812/travel-data-agent.git
cd travel-data-agent

# 安装依赖（需要 Python 3.13+）
uv sync
```

### 2. 配置文件

```bash
# 复制示例配置
cp conf/app_config.yaml.example conf/app_config.yaml

# 编辑配置文件
# - 数据库连接信息
# - LLM API Key
# - Embedding 模型路径
```

### 3. 启动依赖服务

```bash
# 启动 MySQL + Qdrant + Elasticsearch
docker compose up -d
```

### 4. 初始化数据

```bash
# 生成业务数据
cd travel-data
uv run init_db.py
uv run -m generate.main --profile full
cd ..

# 构建元数据 + 向量索引
uv run python -m app.scripts.build_meta_knowledge -c conf/meta_config.travel.yaml
```

### 5. 启动服务

```bash
uv run python -m main
```

访问 http://localhost:8000/ 开始使用。

## 项目结构

```
data-agent/
├── app/
│   ├── agent/           # LangGraph 工作流
│   │   ├── nodes/       # 处理节点（12个）
│   │   ├── graph.py     # 图编排
│   │   └── state.py     # 状态定义
│   ├── api/             # FastAPI 路由
│   │   ├── routers/     # API 路由
│   │   ├── schemas/     # 数据模型
│   │   └── templates/   # 前端页面
│   ├── clients/         # 服务客户端
│   ├── conf/            # 配置 schema
│   ├── core/            # 基础设施
│   ├── entities/        # 领域实体
│   ├── models/          # ORM 模型
│   ├── prompts/         # Prompt 模板
│   ├── repositories/    # 数据访问层
│   ├── scripts/         # 工具脚本
│   └── services/        # 业务服务
├── conf/                # 配置文件
├── docker/              # Docker 配置
├── test/                # 测试和评测
├── travel-data/         # 业务数据生成（可选）
├── docker-compose.yaml  # 服务编排
├── main.py              # 应用入口
└── pyproject.toml       # 项目配置
```

## API 接口

| 接口 | 方法 | 说明 |
|------|------|------|
| `/` | GET | 前端页面 |
| `/api/query` | POST | 流式查询（SSE） |
| `/api/query/json` | POST | JSON 查询 |
| `/docs` | GET | API 文档（Swagger） |

### 查询示例

```bash
curl -X POST http://localhost:8000/api/query/json \
  -H "Content-Type: application/json" \
  -d '{"query": "本月订单量是多少"}'
```

响应：
```json
{
  "query": "本月订单量是多少",
  "intent": "simple",
  "result_type": "table",
  "sql": "SELECT COUNT(*) AS order_count FROM orders WHERE ...",
  "columns": ["order_count"],
  "data": [{"order_count": 30913}],
  "row_count": 1,
  "tables": ["orders"],
  "metrics": ["订单量"]
}
```

## 配置说明

配置文件 `conf/app_config.yaml` 包含以下部分：

```yaml
logging:
  console:
    enable: true
    level: INFO

db_meta:
  host: 127.0.0.1
  port: 3306
  user: root
  password: "your_password"
  database: meta

db_dw:
  host: 127.0.0.1
  port: 3306
  user: root
  password: "your_password"
  database: travel

qdrant:
  host: 127.0.0.1
  port: 6333
  embedding_size: 1024

embedding:
  model_path: /path/to/bge-large-zh-v1.5

es:
  host: 127.0.0.1
  port: 9200
  index_name: data_agent

llm:
  model_name: deepseek-v4-flash
  api_key: your_api_key
  base_url: https://api.deepseek.com
```

## 评测

```bash
# 运行评测脚本
uv run python -m test.evals.run_evals

# 查看评测报告
ls test/evals/reports/
```

## 开发指南

### 添加新的分析能力

1. 在 `app/agent/nodes/` 添加新节点
2. 在 `app/agent/graph.py` 注册节点和边
3. 在 `prompts/` 添加对应的 prompt 模板
4. 更新 `app/api/schemas/query_schema.py` 添加新的结果类型

### 添加新的业务表

1. 在 `conf/meta_config.travel.yaml` 添加表和字段定义
2. 运行 `uv run python -m app.scripts.build_meta_knowledge -c conf/meta_config.travel.yaml`
3. 重启服务

## 已知问题

- Embedding 模型默认使用 CPU，如有 GPU 可安装 CUDA 版本 PyTorch 加速
- 免费 LLM API 有速率限制，建议使用付费 API

## License

MIT
