"""Search and simple data APIs"""
from typing import List, Optional

from fastapi import APIRouter, HTTPException

from app.utils import get_current_time
from app.api.schemas import (
    SearchRequest,
    SearchResponse,
    SearchResult,
    ScenarioSearchRequest,
    ScenarioSearchResponse,
    ScenarioSearchResult,
    ScheduleSearchRequest,
    ScheduleSearchResponse,
    ScheduleSearchResult,
)
from app.storage.meilisearch_service import MeilisearchService
from app.logger import logger

router = APIRouter(prefix="/v1", tags=["search"])


def _require_meilisearch() -> MeilisearchService:
    service = MeilisearchService()
    if not service.is_available:
        raise HTTPException(
            status_code=503,
            detail="Search service is not available. Please ensure Meilisearch is running.",
        )
    return service


def _build_range_filters(
    field: str,
    greater_or_equal: Optional[str],
    less_or_equal: Optional[str],
) -> List[str]:
    filters: List[str] = []
    if greater_or_equal:
        filters.append(f'{field} >= "{greater_or_equal}"')
    if less_or_equal:
        filters.append(f'{field} <= "{less_or_equal}"')
    return filters


@router.post("/search/messages", response_model=SearchResponse)
@router.post("/search", response_model=SearchResponse, include_in_schema=False)
async def search_messages(request: SearchRequest) -> SearchResponse:
    """Search messages using Meilisearch"""
    try:
        meilisearch = _require_meilisearch()
        results = meilisearch.search(
            query=request.query,
            session_id=request.session_id,
            role=request.role,
            category=request.category,
            limit=request.limit,
            offset=request.offset,
            sort=request.sort,
        )
        
        hits = [
            SearchResult(
                id=hit.get("id"),
                session_id=hit.get("session_id"),
                role=hit.get("role"),
                content=hit.get("content"),
                tool_name=hit.get("tool_name"),
                speaker=hit.get("speaker"),
                tool_call_id=hit.get("tool_call_id"),
                created_at=hit.get("created_at"),
                category=hit.get("category", 0),
            )
            for hit in results.get("hits", [])
        ]
        
        return SearchResponse(
            query=request.query,
            hits=hits,
            estimated_total_hits=results.get("estimatedTotalHits", 0),
            limit=request.limit,
            offset=request.offset,
            processing_time_ms=results.get("processingTimeMs"),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in message search: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.post("/search/scenarios", response_model=ScenarioSearchResponse)
async def search_scenarios(request: ScenarioSearchRequest) -> ScenarioSearchResponse:
    """Search scenarios by content plus filter fields"""
    try:
        meilisearch = _require_meilisearch()
        
        filters: List[str] = ['period_type = "scenario"']
        if request.scenario_id:
            filters.append(f'period_id = "{request.scenario_id}"')
        filters.extend(_build_range_filters("start_at", request.start_from, request.start_to))
        filters.extend(_build_range_filters("end_at", request.end_from, request.end_to))
        
        results = meilisearch.search(
            query=request.query,
            session_id=request.session_id,
            limit=request.limit,
            offset=request.offset,
            sort=request.sort,
            index_name=MeilisearchService.PERIOD_INDEX,
            filters=filters,
        )
        
        hits = [
            ScenarioSearchResult(
                scenario_id=hit.get("period_id") or "",
                session_id=hit.get("session_id"),
                content=hit.get("content"),
                start_at=hit.get("start_at"),
                end_at=hit.get("end_at"),
                created_at=hit.get("created_at"),
            )
            for hit in results.get("hits", [])
        ]
        
        return ScenarioSearchResponse(
            query=request.query,
            hits=hits,
            estimated_total_hits=results.get("estimatedTotalHits", 0),
            limit=request.limit,
            offset=request.offset,
            processing_time_ms=results.get("processingTimeMs"),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in scenario search: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.post("/search/schedules", response_model=ScheduleSearchResponse)
async def search_schedules(request: ScheduleSearchRequest) -> ScheduleSearchResponse:
    """Search schedule entries by content plus filter fields"""
    try:
        meilisearch = _require_meilisearch()
        
        filters: List[str] = ['period_type = "schedule"']
        if request.entry_id:
            filters.append(f'period_id = "{request.entry_id}"')
        filters.extend(_build_range_filters("start_at", request.start_from, request.start_to))
        filters.extend(_build_range_filters("end_at", request.end_from, request.end_to))
        
        results = meilisearch.search(
            query=request.query,
            session_id=request.session_id,
            limit=request.limit,
            offset=request.offset,
            sort=request.sort,
            index_name=MeilisearchService.PERIOD_INDEX,
            filters=filters,
        )
        
        hits = [
            ScheduleSearchResult(
                entry_id=hit.get("period_id") or "",
                session_id=hit.get("session_id"),
                content=hit.get("content"),
                start_at=hit.get("start_at"),
                end_at=hit.get("end_at"),
                created_at=hit.get("created_at"),
            )
            for hit in results.get("hits", [])
        ]
        
        return ScheduleSearchResponse(
            query=request.query,
            hits=hits,
            estimated_total_hits=results.get("estimatedTotalHits", 0),
            limit=request.limit,
            offset=request.offset,
            processing_time_ms=results.get("processingTimeMs"),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in schedule search: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/search/status")
async def search_status():
    """Check Meilisearch service status"""
    try:
        meilisearch = MeilisearchService()  # Get singleton instance
        return {
            "available": meilisearch.is_available,
            "running": meilisearch.is_running(),
            "base_url": meilisearch.base_url
        }
    except Exception as e:
        logger.error(f"Error checking search status: {e}")
        return {
            "available": False,
            "running": False,
            "error": str(e)
        }

