from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from backend.db import get_session
from backend.token_usage import ensure_token_usage_state

router = APIRouter(prefix="/api", tags=["metrics"])


@router.get("/simulation-metrics/{session_id}")
def get_simulation_metrics(session_id: str) -> dict:
    record = get_session(session_id)
    if record is None:
        return JSONResponse(
            status_code=404,
            content={"error_type": "SESSION_NOT_FOUND", "message": "Invalid session_id."},
        )

    token_usage = ensure_token_usage_state(record.state_json)
    return {"session_id": session_id, "simulation_metrics": token_usage}

