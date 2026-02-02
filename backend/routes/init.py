from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import Literal, Optional, Dict, Any

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from google.genai import types
from pydantic import BaseModel

from backend.clients import get_genai_client, get_thinking_config
from backend.db import create_session, save_session
from backend.media import generate_music, generate_scene_image, generate_tts
from backend.prompts.initial_script import SYSTEM_INSTRUCTION
from backend.schemas import InitialScriptOutput
from backend.token_usage import extract_usage_metadata, record_token_usage
from backend.validation import StructuredOutputValidationError, validate_model_json

router = APIRouter(prefix="/api", tags=["init"])


class InitRequest(BaseModel):
    story_text: str
    game_length_mode: Literal["SHORT", "LONG", "INFINITE"]


def _dump_model(model: BaseModel) -> dict:
    if hasattr(model, "model_dump"):
        return model.model_dump()
    return model.dict()


def _session_slug(session_id: str) -> str:
    return session_id.replace("-", "")


@router.post("/init")
def init_game(payload: InitRequest) -> dict:
    target_turns_hint = {
        "SHORT": 10,
        "LONG": 20,
        "INFINITE": None,
    }[payload.game_length_mode]

    client = get_genai_client()

    response = client.models.generate_content(
        model="gemini-3-flash-preview",
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_INSTRUCTION,
            response_mime_type="application/json",
            response_json_schema=InitialScriptOutput.model_json_schema(),
            thinking_config=get_thinking_config(),
        ),
        contents=(
            f"Initial scenario (chosen by the player): {payload.story_text}\n"
            f"Game length mode: {payload.game_length_mode}\n"
            f"Target turns (hint, not mandatory): {target_turns_hint}"
        ),
    )

    try:
        parsed = validate_model_json(response.text, InitialScriptOutput)
    except StructuredOutputValidationError as exc:
        return JSONResponse(status_code=422, content=exc.to_error_payload())

    parsed_dict = _dump_model(parsed)

    initial_scene = parsed.initial_scene
    initial_scene_dict = _dump_model(initial_scene)

    session_state = {
        "main_dramatic_concept": parsed.main_dramatic_concept,
        "core_plot": parsed.core_plot,
        "anchor_events": [
            _dump_model(event) for event in parsed.anchor_events
        ],
        "endings": [
            _dump_model(ending) for ending in parsed.endings
        ],
        "story_memory": None,
        "previous_scenes": [],
        "skills": [_dump_model(skill) for skill in parsed.skills],
        "inventory": [],
        "current_music": initial_scene.music_prompt,
        "turn_number": 1,
        "game_length_mode": payload.game_length_mode,
        "target_turns_hint": target_turns_hint,
        "token_usage": {
            "totals": {
                "input_tokens": 0,
                "thinking_tokens": 0,
                "output_tokens": 0,
                "total_tokens": 0,
            },
            "by_call_type": {},
            "events": [],
        },
    }
    record_token_usage(
        session_state,
        "init_script",
        extract_usage_metadata(response),
        turn_number=1,
    )

    session_id = create_session(session_state)
    session_slug = _session_slug(session_id)

    # Generate initial media in parallel using session-scoped filenames.
    media_paths: Dict[str, Optional[str]] = {"image_path": None, "tts_path": None, "music_path": None}
    try:
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures: Dict[str, Any] = {}
            futures["image_path"] = executor.submit(
                generate_scene_image,
                initial_scene.image_prompt,
                f"{session_slug}_scene_1.png",
            )
            futures["tts_path"] = executor.submit(
                generate_tts,
                initial_scene.text_story,
                f"{session_slug}_tts_1.wav",
            )
            futures["music_path"] = executor.submit(
                generate_music,
                initial_scene.music_prompt,
                f"{session_slug}_music_1.wav",
            )
            for key, future in futures.items():
                result = future.result()
                media_paths[key] = str(result) if result is not None else None
    except Exception as exc:  # pragma: no cover - surface as API error
        return JSONResponse(
            status_code=500,
            content={
                "error_type": "MEDIA_GENERATION_FAILED",
                "message": str(exc),
            },
        )
    session_state["previous_scenes"] = [
        {
            "number_of_scene": 1,
            "text_story": initial_scene.text_story,
            "selected_action": None,
            "media": {
                "media_type": "image",
                "image_path": media_paths["image_path"],
                "tts_path": media_paths["tts_path"],
                "music_path": media_paths["music_path"],
            },
        }
    ]
    save_session(session_id, session_state)

    return {
        "session_id": session_id,
        "initial_script": parsed_dict,
        "initial_scene": initial_scene_dict,
        "initial_media": media_paths,
        "simulation_metrics": session_state["token_usage"],
    }
