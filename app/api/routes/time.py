"""Time management API routes"""
from fastapi import APIRouter, HTTPException

from app.api.schemas import (
    TimeActionModel,
    TimeClockRequest,
    TimeClockResponse,
    TimeSeekRequest,
    TimeNudgeRequest,
    TimeSpeedRequest,
)
from app.utils.time_provider import time_provider, TimeAction
from app.storage.session_clock_repository import SessionClockRepository
from app.utils import get_current_time, get_real_time
from app.logger import logger

router = APIRouter(prefix="/v1/sessions", tags=["time"])
clock_repo = SessionClockRepository()


def _actions_to_schema(clock) -> list[TimeActionModel]:
    return [
        TimeActionModel(type=action.type, value=action.value, note=action.note)
        for action in clock.actions
    ]


def _persist_clock(session_id: str, clock):
    clock_repo.insert_or_update_clock(
        session_id=session_id,
        base_virtual=clock.base_virtual.strftime('%Y-%m-%d %H:%M:%S'),
        base_real=clock.base_real.strftime('%Y-%m-%d %H:%M:%S'),
        actions=[action.to_dict() for action in clock.actions],
    )


def _build_response(session_id: str, clock) -> TimeClockResponse:
    current_virtual = get_current_time(session_id=session_id)
    current_real = get_real_time()
    return TimeClockResponse(
        session_id=session_id,
        base_virtual=clock.base_virtual.strftime('%Y-%m-%d %H:%M:%S'),
        base_real=clock.base_real.strftime('%Y-%m-%d %H:%M:%S'),
        actions=_actions_to_schema(clock),
        current_virtual_time=current_virtual,
        current_real_time=current_real,
        updated_at=clock.updated_at,
        real_updated_at=clock.real_updated_at,
    )


def _legacy_actions_from_request(request: TimeClockRequest) -> list[dict]:
    actions: list[dict] = []
    if request.mode == "offset" and request.offset_seconds is not None:
        actions.append({"type": "offset", "value": request.offset_seconds})
    elif request.mode == "scaled" and request.speed is not None:
        actions.append({"type": "scale", "value": request.speed})
    elif request.mode == "fixed":
        actions.append({"type": "freeze", "value": 0})

    if request.mode is None:
        if request.offset_seconds is not None:
            actions.append({"type": "offset", "value": request.offset_seconds})
        if request.speed is not None:
            actions.append({"type": "scale", "value": request.speed})
    return actions


@router.get("/{session_id}/time", response_model=TimeClockResponse)
async def get_session_time(session_id: str):
    """Get current virtual time and clock configuration for a session"""
    try:
        clock = time_provider.get_session_clock(session_id)
        return _build_response(session_id, clock)
    except Exception as e:
        logger.error(f"Error getting session time: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.put("/{session_id}/time", response_model=TimeClockResponse)
async def update_session_time(session_id: str, request: TimeClockRequest):
    """Update session clock configuration"""
    try:
        base_virtual = request.base_virtual or request.fixed_time or request.virtual_start
        actions_payload = None
        if request.actions is not None:
            actions_payload = [action.model_dump() for action in request.actions]
        else:
            legacy_actions = _legacy_actions_from_request(request)
            if legacy_actions:
                actions_payload = legacy_actions

        if request.reset_actions and actions_payload is not None:
            clock = time_provider.update_session_clock(
                session_id=session_id,
                base_virtual=base_virtual,
                actions=actions_payload,
                rebase_current=request.rebase,
            )
        else:
            clock = time_provider.update_session_clock(
                session_id=session_id,
                base_virtual=base_virtual,
                actions=None,
                rebase_current=request.rebase,
            )
            if actions_payload:
                for action_dict in actions_payload:
                    clock = time_provider.append_action(
                        session_id,
                        TimeAction.from_dict(action_dict),
                    )

        _persist_clock(session_id, clock)
        return _build_response(session_id, clock)
    except Exception as e:
        logger.error(f"Error updating session time: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.post("/{session_id}/time/seek", response_model=TimeClockResponse)
async def seek_session_time(session_id: str, request: TimeSeekRequest):
    """Seek to a specific virtual time point"""
    try:
        clock = time_provider.seek(session_id=session_id, virtual_time=request.virtual_time)
        
        _persist_clock(session_id, clock)
        return _build_response(session_id, clock)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error seeking session time: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.post("/{session_id}/time/nudge", response_model=TimeClockResponse)
async def nudge_session_time(session_id: str, request: TimeNudgeRequest):
    """Nudge time forward or backward by delta seconds"""
    try:
        clock = time_provider.nudge(session_id=session_id, delta_seconds=request.delta_seconds)
        _persist_clock(session_id, clock)
        return _build_response(session_id, clock)
    except Exception as e:
        logger.error(f"Error nudging session time: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.post("/{session_id}/time/speed", response_model=TimeClockResponse)
async def set_session_time_speed(session_id: str, request: TimeSpeedRequest):
    """Set time speed multiplier"""
    try:
        clock = time_provider.set_speed(session_id=session_id, speed=request.speed)
        _persist_clock(session_id, clock)
        return _build_response(session_id, clock)
    except Exception as e:
        logger.error(f"Error setting session time speed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

