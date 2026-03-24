from dataclasses import dataclass
from pathlib import Path


@dataclass
class File:
    enable: bool
    level: str
    path: str
    rotation: str
    retention: str

@dataclass
class Console:
    enable: bool
    level: str


@dataclass
class LoggingConfig:
    file: File
    console: Console



# 数据库配置
@dataclass
class DBConfig:
    host: str
    port: int
    user: str
    password: str
    database: str


@dataclass
class QdrantConfig:
    host: str
    port: int
    embedding_size: int


@dataclass
class EmbeddingConfig:
    host: str
    port: int
    model: str


@dataclass
class ESConfig:
    host: str
    port: int
    index_name: str


@dataclass
class LLMConfig:
    model_name: str
    api_key: str


@dataclass
class AppConfig:
    logging: LoggingConfig
    db_meta: DBConfig
    db_dw: DBConfig
    qdrant: QdrantConfig
    embedding: EmbeddingConfig
    es: ESConfig
    llm: LLMConfig

# 案例需求：读取app_config.yaml用户信息
from omegaconf import OmegaConf

# 1.加载指定目录配置文件得到omegaConf对象 通过键名获取 不方便
context = OmegaConf.load(Path(__file__).parents[2] / 'conf' / 'app_config.yaml')

# 2.从结构化对象加载omegaConf对象
structured = OmegaConf.structured(AppConfig)

# 3. 通过OmegaConf.merge()方法将omegaConf对象和结构化对象进行合并 #4. 转为dataclasss对象
# 将应用配置对象app_config 对外提供调用
app_config: AppConfig = OmegaConf.to_object(OmegaConf.merge(structured, context))

# if __name__ == '__main__':
#     print(app_config.db_dw)
