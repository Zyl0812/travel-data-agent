from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path

from app.api.dependencies import get_query_service
from app.api.schemas.query_schema import QueryRequest, QueryResponse
from app.services.query_service import QueryService

query_router = APIRouter()

# 模板目录
templates = Jinja2Templates(directory=Path(__file__).parent.parent / "templates")


@query_router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """首页 - 问数演示页面"""
    return templates.TemplateResponse(request=request, name="index.html")


@query_router.post("/api/query")
async def query_stream(body: QueryRequest, query_service: QueryService = Depends(get_query_service)):
    """流式查询接口"""
    return StreamingResponse(query_service.query(body.query), media_type='text/event-stream')


@query_router.post("/api/query/json", response_model=QueryResponse)
async def query_json(body: QueryRequest, query_service: QueryService = Depends(get_query_service)):
    """JSON 查询接口 - 用于前端页面"""
    result = await query_service.query_json(body.query)
    return result