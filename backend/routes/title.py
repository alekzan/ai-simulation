from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from google.genai import types

from backend.clients import get_genai_client, get_thinking_config
from backend.prompts.title_screen_selector import PROMPT
from backend.schemas import TitleScreenSelectorOutput
from backend.validation import StructuredOutputValidationError, validate_model_json

router = APIRouter(prefix="/api", tags=["title"])


@router.post("/title-options")
def title_options() -> dict:
    client = get_genai_client()

    response = client.models.generate_content(
        model="gemini-3-flash-preview",
        contents=PROMPT,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_json_schema=TitleScreenSelectorOutput.model_json_schema(),
            thinking_config=get_thinking_config(),
        ),
    )

    try:
        parsed = validate_model_json(response.text, TitleScreenSelectorOutput)
    except StructuredOutputValidationError as exc:
        return JSONResponse(status_code=422, content=exc.to_error_payload())

    return parsed.model_dump()
