from langgraph.runtime import Runtime
from datetime import datetime

from app.agent.context import DataAgentContext
from app.agent.state import DataAgentState, DateInfoState, DBInfoState
from app.core.log import logger
from app.repositories.mysql.meta.meta_mysql_repository import MetaMySQLRepository

async def add_extra_context(state: DataAgentState, runtime: Runtime[DataAgentContext]):
    writer = runtime.stream_writer
    writer({"type": "progress", "step": "添加额外上下文信息", "status": "running"})
    
    dw_mysql_repository = runtime.context['dw_mysql_repository']
    meta_mysql_repository = runtime.context['meta_mysql_repository']
    
    # 1. 获取当前时间：日期、星期、季度
    try:
        # 当前的时间信息
        today: datetime = datetime.today()
        # 日期
        date = today.strftime("%Y-%m-%d")
        # 星期
        weekday = today.strftime("%A")
        # 季度
        quarter = f"Q{(today.month - 1) // 3 + 1}"
        
        date_info = DateInfoState(date=date, weekday=weekday, quarter=quarter)
        
        # 2. 获取数据库信息：DW数据库管理系统名称、数据库版本
        db_info:dict[str, str] = await dw_mysql_repository.get_db_info()
        db_info_state = DBInfoState(**db_info)
        
        # 3. 获取枚举值字典
        enum_columns = await meta_mysql_repository.get_enum_columns()
        enum_values = {}
        for col in enum_columns:
            if col.examples and len(col.examples) > 0:
                # 构建字段标识：table_id.column_name
                field_key = f"{col.table_id}.{col.name}"
                enum_values[field_key] = col.examples
        
        # 4. 获取所有表的字段列表
        table_columns = await meta_mysql_repository.get_all_tables_with_columns()
        
        writer({"type": "progress", "step": "添加额外上下文信息", "status": "success"})
        logger.info(f'额外上下文信息：{date_info}, {db_info_state}, 枚举值字段数：{len(enum_values)}, 表字段字典：{len(table_columns)}')
        # 5. 更新 state：date_info, db_info, enum_values, table_columns
        return {"date_info": date_info, "db_info": db_info_state, "enum_values": enum_values, "table_columns": table_columns}
    
    except Exception as e:
        writer({"type": "progress", "step": "添加额外上下文信息", "status": "error"})
        logger.error(f'添加上下文失败：{str(e)}')
        raise