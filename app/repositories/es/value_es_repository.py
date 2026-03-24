from dataclasses import asdict

from elasticsearch import AsyncElasticsearch

from app.entities.value_info import ValueInfo


class ValueESRepository:
    """用于操作ES数据库的持久层"""

    index_name = "data-agent-column"
    index_mappings = {
        "dynamic": False,
        "properties": {
            "id": {"type": "keyword"},
            "value": {
                "type": "text",
                "analyzer": "ik_max_word",
                "search_analyzer": "ik_max_word",
            },
            "column_id": {"type": "keyword"},
        },
    }

    def __init__(self, client: AsyncElasticsearch):
        self.client = client

    async def ensure_index(self):
        if not await self.client.indices.exists(index=self.index_name):
            await self.client.indices.create(
                index=self.index_name, mappings=self.index_mappings
            )

    async def upsert(self, values_infos: list[ValueInfo], batch_size: int = 10):
        for i in range(0, len(values_infos), batch_size):
            batch = values_infos[i : i + batch_size]
            operations = []

            for value_info in batch:
                operations.append(
                    {"index": {"_index": self.index_name, "_id": value_info.id}}
                )
                operations.append(asdict(value_info))
            await self.client.bulk(operations=operations)
