from typing import cast

from sqlalchemy import Result, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


class DWMySQLRepository:
    """用于操作dw数据库持久层"""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self.session_factory = session_factory

    async def get_column_types(self, table_name: str) -> dict[str, str]:
        """根据表明获取该表所有字段类型"""
        sql = f"SHOW COLUMNS FROM {table_name}"
        result = await self.session.execute(text(sql))
        return {column.Field: column.Type for column in result.fetchall()}

    async def get_column_values(
        self, table_name: str, column_name: str, limit: int = 10
    ) -> list[str]:
        """根据表名和字段名获取该字段部分取值"""
        sql = f"SELECT DISTINCT {column_name} FROM {table_name} LIMIT {limit}"
        result: Result = await self.session.execute(text(sql))
        return cast(list[str], result.scalars().fetchall())
