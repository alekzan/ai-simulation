from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse


def get_request_api_key(request: Request) -> str | None:
    value = request.headers.get("X-Gemini-Api-Key", "").strip()
    return value or None


def missing_api_key_response() -> JSONResponse:
    return JSONResponse(
        status_code=401,
        content={
            "error_type": "MISSING_API_KEY",
            "message": "Simulation access key required. Provide a Gemini API key to continue.",
        },
    )
