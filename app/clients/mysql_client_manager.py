import asyncio

from typing import Optional
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.conf.app_config import DBConfig, app_config


class MySQLClientManager:
    
    def __init__(self, db_config: DBConfig):
        # 通过构造函数传入数据库配置
        self.db_config = db_config
        # 设计engine实例属性
        self.engine: Optional[AsyncEngine] = None
        self.session_factory: Optional[async_sessionmaker] = None
        
    
    def _get_url(self):
        return f"mysql+asyncmy://{self.db_config.user}:{self.db_config.password}@{self.db_config.host}:{self.db_config.port}/{self.db_config.database}?charset=utf8mb4"
    
    def init(self):
        # 初始化engine
        self.engine = create_async_engine(self._get_url(),echo=True)
        self.session_factory = async_sessionmaker(self.engine)
        
    
    async def close(self):
        if self.engine:
            await self.engine.dispose()
    

dw_mysql_client_manager = MySQLClientManager(app_config.db_dw)
meta_mysql_client_manager = MySQLClientManager(app_config.db_meta)


if __name__ == "__main__":
    dw_mysql_client_manager.init()
    
    # async def test_by_engine():
    #     async with AsyncSession(dw_mysql_client_manager.engine) as dw_session:
    #         result = await dw_session.execute(text('show tables;'))            
    #         print(result.scalars().fetchall())
    #         await dw_mysql_client_manager.close()
    
    # asyncio.run(test_by_engine())
    
    async def test_by_session_maker():
        async with dw_mysql_client_manager.session_factory() as dw_session:
            result = await dw_session.execute(text('show tables;'))            
            print(result.scalars().fetchall())
            await dw_mysql_client_manager.close()
    
    asyncio.run(test_by_session_maker())