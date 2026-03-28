from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from app.api.dependencies import get_query_service
from app.api.schemas.query_schema import QuerySchema
from app.services.query_service import QueryService

query_router = APIRouter()

@query_router.post("/api/query")
async def query(body: QuerySchema, query_service: QueryService = Depends(get_query_service)):
    '''
    前后端约定提交参数采用请求体{"query": "统计各分类销售额"}
    Args:
        body (QuerySchema): 查询参数
    Returns:
        StreamingResponse: 查询结果，异步流式返回，约定{type:'progress', step:'召回字段', status:'success'}
    '''
    return StreamingResponse(query_service.query(body.query), media_type='text/event-stream')