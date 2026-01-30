from __future__ import annotations

from typing import Literal

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from google.genai import types
from pydantic import BaseModel

from backend.clients import get_genai_client, get_thinking_config
from backend.db import create_session
from backend.prompts.initial_script import SYSTEM_INSTRUCTION
from backend.schemas import InitialScriptOutput
from backend.validation import StructuredOutputValidationError, validate_model_json

router = APIRouter(prefix="/api", tags=["init"])


class InitRequest(BaseModel):
    story_text: str
    game_length_mode: Literal["SHORT", "LONG", "INFINITE"]


def _dump_model(model: BaseModel) -> dict:
    if hasattr(model, "model_dump"):
        return model.model_dump()
    return model.dict()


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
        "previous_scenes": [
            {
                "number_of_scene": 1,
                "text_story": initial_scene.text_story,
                "selected_action": None,
            }
        ],
        "skills": [_dump_model(skill) for skill in parsed.skills],
        "inventory": [],
        "current_music": initial_scene.music_prompt,
        "turn_number": 1,
        "game_length_mode": payload.game_length_mode,
        "target_turns_hint": target_turns_hint,
    }

    session_id = create_session(session_state)

    return {
        "session_id": session_id,
        "initial_script": parsed_dict,
        "initial_scene": initial_scene_dict,
    }
