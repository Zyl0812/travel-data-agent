# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**data-agent** is an AI-powered data agent application that uses LLMs (LangChain + DeepSeek) to interact with databases and perform intelligent queries. It integrates multiple services: MySQL databases, vector embeddings, Elasticsearch, and Qdrant vector DB.

## Architecture

### Core Components

1. **Configuration Management** (`app/conf/app_config.py`)
   - Uses OmegaConf + dataclasses for strongly-typed config
   - Merges YAML config (`conf/app_config.yaml`) with structured schema
   - Exports `app_config` object for application use
   - Config sections: logging, db_meta, db_dw, qdrant, embedding, es, llm

2. **Client Managers** (`app/clients/`)
   - `EmbeddingClientManager`: HuggingFace endpoint embeddings wrapper
   - `MySQLClientManager`: Async SQLAlchemy engine for MySQL (supports db_meta and db_dw)
   - `QdrantClientManager`: Async Qdrant vector DB client
   - All managers follow init() + singleton pattern, test code in `if __name__ == "__main__"`

3. **Dependencies**
   - **LLM/AI**: langchain, langchain-deepseek, langchain-huggingface, langgraph
   - **Databases**: sqlalchemy (async), asyncmy (MySQL driver), qdrant-client, elasticsearch[async]
   - **Config**: omegaconf, pyyaml
   - **Utilities**: jieba (Chinese text), huggingface-hub, loguru, fastapi[standard], cryptography

## Development Setup

**Python Version**: 3.13

**Package Manager**: uv (see `pyproject.toml` and `uv.lock`)

```bash
# Install dependencies
uv sync

# Activate virtual environment
source .venv/Scripts/activate  # Windows
source .venv/bin/activate       # Unix

# Run client tests directly (check __main__ blocks)
python -m app.clients.embedding_client_manager
python -m app.clients.mysql_client_manager
python -m app.clients.qdrant_client_manager
```

## Configuration

**Location**: `conf/app_config.yaml`

Key sections:
- `logging`: File and console logging config (loguru integration)
- `db_meta` / `db_dw`: MySQL credentials for metadata and data warehouse databases
- `qdrant`: Vector DB host/port and embedding size
- `embedding`: HuggingFace endpoint for embeddings
- `es`: Elasticsearch config
- `llm`: LLM model name and API key (currently DeepSeek)

To add new config sections:
1. Define dataclass in `app/conf/app_config.py`
2. Add to `AppConfig` dataclass
3. Add YAML entry to `conf/app_config.yaml`
4. Call `OmegaConf.to_object()` to access typed config

## Directory Structure

```
app/
├── __init__.py
├── conf/
│   └── app_config.py          # Config schema & loading
├── clients/                   # Service clients
│   ├── embedding_client_manager.py
│   ├── mysql_client_manager.py
│   └── qdrant_client_manager.py
└── core/                      # Ready for business logic
conf/
└── app_config.yaml            # Runtime configuration
test/                          # Test directory (empty)
logs/                          # Application logs
```

## Key Patterns

- **Async-first**: All clients use async/await (asyncmy, AsyncQdrantClient, etc.)
- **Config injection**: Clients accept config objects via constructor
- **Singleton instances**: Each manager creates module-level singleton (e.g., `embedding_client_manager`)
- **Test-driven client code**: Each client has runnable test code in `if __name__ == "__main__"`

## Notes

- MySQL connections use `async_sessionmaker` pattern for managing sessions
- Qdrant uses cosine distance for vector similarity by default
- HuggingFace embeddings run on external service (not embedded)
- app/core/ is empty and ready for agent implementation
- Credentials in YAML (db passwords, API keys) should be externalized for production
