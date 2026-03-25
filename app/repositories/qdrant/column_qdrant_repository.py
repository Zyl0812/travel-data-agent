from dataclasses import asdict
from qdrant_client import AsyncQdrantClient
from qdrant_client.http.models import Distance, VectorParams
from qdrant_client.models import PointStruct

from app.conf.app_config import app_config
from app.entities.column_info import ColumnInfo


class ColumnQdrantRepository:
    """用于操作字段信息向量集合持久层"""

    collection_name = "data-agent-column"

    def __init__(self, client: AsyncQdrantClient):
        self.client = client

    async def ensure_collection(self):
        if await self.client.collection_exists(collection_name=self.collection_name):
            pass
        else:
            await self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(
                    size=app_config.qdrant.embedding_size, distance=Distance.COSINE
                ),
            )
            
    async def upsert(self, ids:list[str], embeddings:list[list[float]], payloads:list[ColumnInfo], batch_size: int=10):
        # 1. 用zip按索引打包为元组迭代器 [(id, vector, payload)]
        zipped = list(zip(ids, embeddings, payloads))
        
        # 2. 分批次插入
        for i in range(0, len(zipped), batch_size):
            batch = zipped[i:i+batch_size]
            points = [PointStruct(
                id=id,
                vector=embedding,
                payload=asdict(payload)
            ) for id, embedding, payload in batch]
            
            await self.client.upsert(
                collection_name=self.collection_name,
                points=points,
            )
    
    async def search(self, embedding: list[float], score: float=0.7, limit: int = 10) -> list[ColumnInfo]:
        result = await self.client.query_points(
            collection_name=self.collection_name,
            query=embedding,
            limit=limit,
            score_threshold=score,
        )
        
        return [ColumnInfo(**point.payload) for point in result.points if point.payload is not None]
        