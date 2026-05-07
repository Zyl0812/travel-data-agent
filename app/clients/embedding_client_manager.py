from langchain_huggingface.embeddings import HuggingFaceEmbeddings
from typing import Optional

from app.conf.app_config import app_config
from app.core.log import logger


class EmbeddingClientManager:

    def __init__(self):
        self.client: Optional[HuggingFaceEmbeddings] = None

    def init(self):
        model_name = app_config.embedding.model_path
        device = self._pick_device()
        logger.info(f"Embedding 模型: {model_name} | device={device}")
        self.client = HuggingFaceEmbeddings(
            model_name=model_name,
            model_kwargs={"device": device},
            encode_kwargs={"batch_size": 64, "normalize_embeddings": True},
        )

    @staticmethod
    def _pick_device() -> str:
        """优先 cuda → mps → cpu。需要 PyTorch 是 CUDA 版本才能用 GPU。"""
        try:
            import torch
        except ImportError:
            return "cpu"
        if torch.cuda.is_available():
            return "cuda"
        if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            return "mps"
        return "cpu"
        
        
embedding_client_manager = EmbeddingClientManager()

# if __name__ == "__main__":
#     embedding_client_manager.init()
#     client = embedding_client_manager.client
    
#     async def test_embedding():
#         # result = await client.aembed_query('你好')
        
#         # result = await client.aembed_documents(['你好', 'hello'])
#         # print(result)
        
#         list1 = [f'数字{i}' for i in range(25)]
        
#         # 采用分批次方式，每次对10个字符串进行embedding
#         batch_size = 10
#         for i in range(0, len(list1), batch_size):
#             batch = list1[i:i+batch_size]
#             result = await client.aembed_documents(batch)
#             print(result)
        
    
#     asyncio.run(test_embedding())