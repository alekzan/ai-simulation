from __future__ import annotations

import random
from concurrent.futures import ThreadPoolExecutor

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from google.genai import types

from backend.clients import get_genai_client, get_thinking_config
from backend.ephemeral_media import (
    EPHEMERAL_IMAGE_TTL_SECONDS,
    build_ephemeral_path,
    prune_expired_media,
    store_media,
)
from backend.media import cleanup_expired_media, generate_scene_image_bytes
from backend.prompts.title_screen_selector import PROMPT
from backend.request_auth import get_request_api_key, missing_api_key_response
from backend.schemas import TitleScreenSelectorOutput
from backend.validation import StructuredOutputValidationError, validate_model_json

router = APIRouter(prefix="/api", tags=["title"])


def _is_development_mode() -> bool:
    import os

    env = os.getenv("APP_ENV", "development").strip().lower()
    return env not in {"production", "prod"}


def _use_dev_fixed_titles() -> bool:
    import os

    if not _is_development_mode():
        return False
    raw = os.getenv("TITLE_DEV_FIXED_OPTIONS", "true").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def _dev_fixed_ideas() -> list[dict]:
    return [
        {
            "id": "A",
            "title": "Velvet Coup",
            "one_liner": "On gala night, you must unmask a palace conspiracy before dawn crowns the wrong heir.",
            "cover_image_prompt": "",
            "cover_image_path": "media/images/title_acff3de5_A.png",
        },
        {
            "id": "B",
            "title": "Last Train to Aragon",
            "one_liner": "A stolen ledger and one overnight train decide whether your family name survives the morning papers.",
            "cover_image_prompt": "",
            "cover_image_path": "media/images/title_acff3de5_B.png",
        },
        {
            "id": "C",
            "title": "Ashes at Noon",
            "one_liner": "As wildfire surrounds your town, you must choose who gets the last safe route out.",
            "cover_image_prompt": "",
            "cover_image_path": "media/images/title_acff3de5_C.png",
        },
    ]


def _build_title_generation_contents() -> str:
    genre_triplets = [
        ("political thriller", "historical drama", "survival adventure"),
        ("heist thriller", "fantasy court intrigue", "grounded mystery"),
        ("sports drama", "period adventure", "crime procedural"),
        ("romantic drama", "expedition adventure", "urban mystery"),
        ("spy thriller", "family drama", "frontier western"),
    ]
    g1, g2, g3 = random.choice(genre_triplets)
    diversity_directive = (
        "\n\nDIVERSITY ENFORCEMENT\n"
        "Generate one idea per slot with distinct primary genres:\n"
        f"- Idea A primary genre: {g1}\n"
        f"- Idea B primary genre: {g2}\n"
        f"- Idea C primary genre: {g3}\n"
        "Do not duplicate a primary genre across slots.\n"
    )
    return PROMPT + diversity_directive


def _generate_title_ideas(api_key: str) -> TitleScreenSelectorOutput:
    client = get_genai_client(api_key=api_key)

    response = client.models.generate_content(
        model="gemini-3-flash-preview",
        contents=_build_title_generation_contents(),
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_json_schema=TitleScreenSelectorOutput.model_json_schema(),
            thinking_config=get_thinking_config(),
        ),
    )

    return validate_model_json(response.text, TitleScreenSelectorOutput)


@router.post("/title-options")
def title_options(request: Request) -> dict:
    api_key = get_request_api_key(request)
    if not api_key:
        return missing_api_key_response()
    cleanup_expired_media()
    prune_expired_media()

    if _use_dev_fixed_titles():
        return {
            "ideas": [
                {
                    "id": idea["id"],
                    "title": idea["title"],
                    "one_liner": idea["one_liner"],
                    "cover_image_prompt": idea["cover_image_prompt"],
                }
                for idea in _dev_fixed_ideas()
            ]
        }

    try:
        parsed = _generate_title_ideas(api_key)
    except StructuredOutputValidationError as exc:
        return JSONResponse(status_code=422, content=exc.to_error_payload())
    except Exception as exc:
        return JSONResponse(
            status_code=502,
            content={"error_type": "MODEL_CALL_FAILED", "message": str(exc)},
        )

    return parsed.model_dump()


@router.post("/title-options-with-covers")
def title_options_with_covers(request: Request) -> dict:
    api_key = get_request_api_key(request)
    if not api_key:
        return missing_api_key_response()
    cleanup_expired_media()
    prune_expired_media()

    if _use_dev_fixed_titles():
        return {"ideas": _dev_fixed_ideas()}

    try:
        parsed = _generate_title_ideas(api_key)
    except StructuredOutputValidationError as exc:
        return JSONResponse(status_code=422, content=exc.to_error_payload())
    except Exception as exc:
        return JSONResponse(
            status_code=502,
            content={"error_type": "MODEL_CALL_FAILED", "message": str(exc)},
        )

    cover_paths: dict[str, str | None] = {idea.id: None for idea in parsed.ideas}
    try:
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = {
                idea.id: executor.submit(
                    generate_scene_image_bytes,
                    idea.cover_image_prompt,
                    api_key,
                    "9:16",
                )
                for idea in parsed.ideas
            }
            for idea_id, future in futures.items():
                image_bytes = future.result()
                token = store_media(
                    image_bytes,
                    "image/png",
                    EPHEMERAL_IMAGE_TTL_SECONDS,
                )
                cover_paths[idea_id] = build_ephemeral_path(token)
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
