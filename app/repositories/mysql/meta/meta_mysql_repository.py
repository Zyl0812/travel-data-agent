from sqlalchemy import text, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.entities.column_info import ColumnInfo
from app.entities.column_metric import ColumnMetric
from app.entities.metric_info import MetricInfo
from app.entities.table_info import TableInfo
from app.models.column_info_mysql import ColumnInfoMySQL
from app.models.table_info_mysql import TableInfoMySQL
from app.repositories.mysql.meta.mappers.column_info_mapper import ColumnInfoMapper
from app.repositories.mysql.meta.mappers.column_metric_mapper import ColumnMetricMapper
from app.repositories.mysql.meta.mappers.metric_info_mapper import MetricInfoMapper
from app.repositories.mysql.meta.mappers.table_info_mapper import TableInfoMapper


class MetaMySQLRepository:
    """用于操作meta数据库"""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def begin(self):
        return self.session.begin()

    async def truncate_all(self):
        """清空所有 meta 表数据（按外键依赖顺序）"""
        tables = ["column_metric", "column_info", "metric_info", "table_info"]
        for table in tables:
            await self.session.execute(text(f"TRUNCATE TABLE `{table}`"))
        await self.session.commit()

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
        
    async def get_column_info_by_id(self, column_id: str) -> ColumnInfo:
        column_info_mysql: ColumnInfoMySQL | None = await self.session.get(ColumnInfoMySQL, column_id)

        if column_info_mysql is None:
            raise ValueError(f"ColumnInfo with id {column_id} not found")

        return ColumnInfoMapper.to_entity(column_info_mysql)
    
    
    async def get_key_columns_by_table_id(self, table_id: str) -> list[ColumnInfo]:
        stmt = select(ColumnInfoMySQL).where(ColumnInfoMySQL.table_id == table_id, ColumnInfoMySQL.role.in_(['primary_key', 'foreign_key']))
        
        result = await self.session.scalars(stmt)
        
        return [ColumnInfoMapper.to_entity(column_info_mysql) for column_info_mysql in result.all()]
    
    async def get_table_info_by_id(self, table_id: str) -> TableInfo:
        table_info_mysql: TableInfoMySQL | None = await self.session.get(TableInfoMySQL, table_id)

        if table_info_mysql is None:
            raise ValueError(f"TableInfo with id {table_id} not found")

        return TableInfoMapper.to_entity(table_info_mysql)

    async def get_enum_columns(self) -> list[ColumnInfo]:
        """获取所有包含枚举值的字段（examples不为空的dimension类型字段）"""
        stmt = select(ColumnInfoMySQL).where(
            ColumnInfoMySQL.role == 'dimension',
            ColumnInfoMySQL.examples.isnot(None)
        )
        result = await self.session.scalars(stmt)
        return [ColumnInfoMapper.to_entity(col) for col in result.all()]

    async def get_all_tables_with_columns(self) -> dict[str, list[str]]:
        """获取所有表及其字段名列表，用于注入到SQL生成prompt"""
        # 获取所有表
        tables_stmt = select(TableInfoMySQL)
        tables_result = await self.session.scalars(tables_stmt)
        tables = tables_result.all()
        
        # 获取所有字段
        columns_stmt = select(ColumnInfoMySQL)
        columns_result = await self.session.scalars(columns_stmt)
        columns = columns_result.all()
        
        # 按表分组
        table_columns: dict[str, list[str]] = {}
        for table in tables:
            table_columns[table.id] = []
        
        for col in columns:
            if col.table_id in table_columns:
                table_columns[col.table_id].append(col.name)
        
        return table_columns
