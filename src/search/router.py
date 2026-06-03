"""Search API endpoints — hybrid search, semantic-only search, and media search."""
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from typing import Optional, Dict

from src.auth.dependencies import get_current_user
from src.search.search_service import hybrid_search, search_media
from src.common.logger import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/search", tags=["search"])


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=500)
    n_results: int = Field(default=10, ge=1, le=50)
    filters: Optional[Dict] = None


@router.post("")
async def search(data: SearchRequest, current_user=Depends(get_current_user)):
    results = await hybrid_search(data.query, n_results=data.n_results, filters=data.filters)
    return {"query": data.query, "count": len(results), "results": results}


@router.post("/semantic")
async def semantic_search(data: SearchRequest, current_user=Depends(get_current_user)):
    from src.search.search_service import _semantic_search
    results = await _semantic_search(data.query, data.n_results, data.filters)
    return {"query": data.query, "count": len(results), "results": results}


@router.post("/media")
async def media_search_endpoint(
    query: str = Query(...),
    media_type: Optional[str] = Query(None, pattern="^(image|video|voice)$"),
    n_results: int = Query(20, ge=1, le=100),
    current_user=Depends(get_current_user),
):
    results = await search_media(query, media_type=media_type, n_results=n_results)
    return {"query": query, "media_type": media_type, "count": len(results), "results": results}
