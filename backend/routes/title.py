from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from google.genai import types

from backend.clients import get_genai_client, get_thinking_config
from backend.media import generate_scene_image
from backend.prompts.title_screen_selector import PROMPT
from backend.schemas import TitleScreenSelectorOutput
from backend.validation import StructuredOutputValidationError, validate_model_json

router = APIRouter(prefix="/api", tags=["title"])


def _generate_title_ideas() -> TitleScreenSelectorOutput:
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

    return validate_model_json(response.text, TitleScreenSelectorOutput)


@router.post("/title-options")
def title_options() -> dict:
    try:
        parsed = _generate_title_ideas()
    except StructuredOutputValidationError as exc:
        return JSONResponse(status_code=422, content=exc.to_error_payload())

    return parsed.model_dump()


@router.post("/title-options-with-covers")
def title_options_with_covers() -> dict:
    try:
        parsed = _generate_title_ideas()
    except StructuredOutputValidationError as exc:
        return JSONResponse(status_code=422, content=exc.to_error_payload())

    batch_id = uuid4().hex[:8]
    cover_paths: dict[str, str | None] = {idea.id: None for idea in parsed.ideas}
    try:
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = {
                idea.id: executor.submit(
                    generate_scene_image,
                    idea.cover_image_prompt,
                    f"title_{batch_id}_{idea.id}.png",
                )
                for idea in parsed.ideas
            }
            for idea_id, future in futures.items():
                result = future.result()
                cover_paths[idea_id] = str(result) if result is not None else None
    except Exception as exc:
        return JSONResponse(
            status_code=500,
            content={"error_type": "MEDIA_GENERATION_FAILED", "message": str(exc)},
        )

    return {
        "ideas": [
            {
                **idea.model_dump(),
                "cover_image_path": cover_paths.get(idea.id),
            }
            for idea in parsed.ideas
        ]
    }
