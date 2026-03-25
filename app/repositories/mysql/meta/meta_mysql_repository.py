from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.entities.column_info import ColumnInfo
from app.entities.column_metric import ColumnMetric
from app.entities.metric_info import MetricInfo
from app.entities.table_info import TableInfo
from app.repositories.mysql.meta.mappers.column_info_mapper import ColumnInfoMapper
from app.repositories.mysql.meta.mappers.column_metric_mapper import ColumnMetricMapper
from app.repositories.mysql.meta.mappers.metric_info_mapper import MetricInfoMapper
from app.repositories.mysql.meta.mappers.table_info_mapper import TableInfoMapper


class MetaMySQLRepository:
    """用于操作meta数据库"""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self.session_factory = session_factory

    async def save_table_infos(self, table_infos: list[TableInfo]):
        # 1. 将业务对象转为ORM模型对象
        table_info_models = [
            TableInfoMapper.to_model(table_info) for table_info in table_infos
        ]

        # 2. 调用框架提供批量保存函数
        self.session.add_all(table_info_models)

    async def save_column_infos(self, column_infos: list[ColumnInfo]):
        # 1. 将业务对象转为ORM模型对象
        column_info_models = [
            ColumnInfoMapper.to_model(column_info) for column_info in column_infos
        ]
        # 2. 调用框架提供批量保存函数
        self.session.add_all(column_info_models)

    async def save_metric_infos(self, metric_infos: list[MetricInfo]):
        models = [
            MetricInfoMapper.to_model(metric_info) for metric_info in metric_infos
        ]
        self.session.add_all(models)

    async def save_column_metric_infos(self, column_metric_infos: list[ColumnMetric]):
        models = [
            ColumnMetricMapper.to_model(column_metric_info)
            for column_metric_info in column_metric_infos
        ]
        self.session.add_all(models)
