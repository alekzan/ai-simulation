from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks
from fastapi.responses import JSONResponse
from google.genai import types
from pydantic import BaseModel

from backend.clients import get_genai_client, get_thinking_config
from backend.db import get_session, save_session
from backend.media import generate_music, generate_scene_image, generate_tts
from backend.prompts.narrator_director import STATIC_PROMPT
from backend.prompts.state_canonicalizer import STATE_CANONICALIZER_SYSTEM
from backend.prompts.story_memory_summarizer import SYSTEM_INSTRUCTION as STORY_MEMORY_SYSTEM
from backend.schemas import (
    CanonicalizerInput,
    CanonicalizerOutput,
    DirectorNarratorOutput,
    FailedInventoryUpdate,
    FailedSkillUpdate,
    StoryMemorySummarizerInput,
    StoryMemorySummarizerOutput,
)
from backend.token_usage import extract_usage_metadata, record_token_usage
from backend.validation import (
    StructuredOutputValidationError,
    validate_model_json,
)

router = APIRouter(prefix="/api", tags=["turn"])


class TurnRequest(BaseModel):
    session_id: str
    action: str


def _dump_model(model: BaseModel) -> dict:
    if hasattr(model, "model_dump"):
        return model.model_dump()
    return model.dict()


def _session_slug(session_id: str) -> str:
    return session_id.replace("-", "")


def _build_dynamic_context(state: dict, recent_scenes: List[dict]) -> str:
    payload = {
        "main_dramatic_concept": state["main_dramatic_concept"],
        "core_plot": state["core_plot"],
        "anchor_events": state["anchor_events"],
        "endings": state["endings"],
        "story_memory": state.get("story_memory"),
        "recent_scenes": recent_scenes,
        "current_music": state["current_music"],
        "skills": state["skills"],
        "inventory": state["inventory"],
        "game_length_mode": state.get("game_length_mode"),
        "target_turns_hint": state.get("target_turns_hint"),
        "turn_number": state["turn_number"],
    }

    return (
        "DYNAMIC CONTEXT (internal, do not repeat back to the player)\n"
        + json.dumps(payload, ensure_ascii=False, indent=2)
    )


def _apply_inventory_changes(
    state: dict,
    changes: list,
) -> tuple[list, list[FailedInventoryUpdate]]:
    inventory = {
        item["name"]: {
            "name": item.get("name"),
            "new_count": item.get("new_count", 0),
            "reason": item.get("reason"),
            "note": item.get("note"),
            "added_turn": item.get("added_turn"),
        }
        for item in state.get("inventory", [])
        if item.get("name")
    }
    failed: list[FailedInventoryUpdate] = []

    for change in changes:
        name = change.name
        prev_item = inventory.get(name)
        prev_count = prev_item.get("new_count", 0) if prev_item else 0

        is_new = prev_count == 0 and change.new_count > 0

        if prev_item is None and not is_new:
            failed.append(
                FailedInventoryUpdate(
                    name=name,
                    new_count=change.new_count,
                    reason=change.reason,
                    note=change.note,
                    added_turn=change.added_turn,
                )
            )
            continue

        if change.new_count <= 0:
            inventory.pop(name, None)
            continue

        updated = {
            "name": name,
            "new_count": change.new_count,
        }
        if is_new:
            updated.update(
                {
                    "reason": change.reason,
                    "note": change.note,
                    "added_turn": change.added_turn,
                }
            )
        else:
            if prev_item:
                updated.update(
                    {
                        "reason": prev_item.get("reason"),
                        "note": prev_item.get("note"),
                        "added_turn": prev_item.get("added_turn"),
                    }
                )
        inventory[name] = updated

    return list(inventory.values()), failed


def _apply_skill_change(
    state: dict,
    skill_change,
) -> tuple[list, Optional[FailedSkillUpdate]]:
    if skill_change is None:
        return state.get("skills", []), None

    skills = state.get("skills", [])
    failed: Optional[FailedSkillUpdate] = None

    target_index = None
    for idx, skill in enumerate(skills):
        if skill["domain"] == skill_change.domain and skill["name"] == skill_change.name:
            target_index = idx
            break

    if target_index is None:
        # Use domain match for canonicalizer new_value calculation (one skill per domain).
        domain_value = 0
        for skill in skills:
            if skill["domain"] == skill_change.domain:
                domain_value = skill.get("value", 0)
                break
        failed = FailedSkillUpdate(
            domain=skill_change.domain,
            name=skill_change.name,
            delta=skill_change.delta,
            new_value=max(0, domain_value + skill_change.delta),
            reason=skill_change.reason,
        )
        return skills, failed

    current_value = skills[target_index].get("value", 0)
    new_value = current_value + skill_change.delta
    if new_value < 0:
        new_value = 0
    if new_value > 10:
        new_value = 10
    skills[target_index]["value"] = new_value
    return skills, None


def _run_canonicalizer(
    canonical_inventory: list[str],
    canonical_skills_by_domain: dict[str, list[str]],
    failed_inventory_updates: list[FailedInventoryUpdate],
    failed_skill_update: Optional[FailedSkillUpdate],
    scene_excerpt: Optional[str],
    player_action: Optional[str],
) -> tuple[CanonicalizerOutput, dict[str, int]]:
    client = get_genai_client()

    payload = CanonicalizerInput(
        canonical_inventory=canonical_inventory,
        canonical_skills_by_domain=canonical_skills_by_domain,
        failed_inventory_updates=failed_inventory_updates,
        failed_skill_update=failed_skill_update,
        scene_excerpt=scene_excerpt,
        player_action=player_action,
    )

    response = client.models.generate_content(
        model="gemini-3-flash-preview",
        config=types.GenerateContentConfig(
            system_instruction=STATE_CANONICALIZER_SYSTEM,
            response_mime_type="application/json",
            response_json_schema=CanonicalizerOutput.model_json_schema(),
            thinking_config=get_thinking_config(),
        ),
        contents=json.dumps(_dump_model(payload), ensure_ascii=False),
    )

    parsed = validate_model_json(response.text, CanonicalizerOutput)
    return parsed, extract_usage_metadata(response)


def _summarize_story_memory(session_id: str) -> None:
    record = get_session(session_id)
    if record is None:
        return

    state = record.state_json
    if state.get("story_memory"):
        return

    previous_scenes = state.get("previous_scenes", [])
    if len(previous_scenes) < 10:
        return

    scenes_to_summarize = []
    for scene in previous_scenes[:10]:
        scenes_to_summarize.append(
            {
                "number_of_scene": scene.get("number_of_scene"),
                "text_story": scene.get("text_story"),
                "selected_action": scene.get("selected_action") or "",
            }
        )

    payload = StoryMemorySummarizerInput(
        main_dramatic_concept=state["main_dramatic_concept"],
        core_plot=state["core_plot"],
        anchor_events=state.get("anchor_events"),
        endings=state.get("endings"),
        scenes_to_summarize=scenes_to_summarize,
        current_story_memory=None,
    )

    client = get_genai_client()
    response = client.models.generate_content(
        model="gemini-3-flash-preview",
        config=types.GenerateContentConfig(
            system_instruction=STORY_MEMORY_SYSTEM,
            response_mime_type="application/json",
            response_json_schema=StoryMemorySummarizerOutput.model_json_schema(),
            thinking_config=get_thinking_config(),
        ),
        contents=json.dumps(_dump_model(payload), ensure_ascii=False),
    )

    try:
        parsed = validate_model_json(response.text, StoryMemorySummarizerOutput)
    except StructuredOutputValidationError:
        return

    record_token_usage(
        state,
        "story_memory_summarizer",
        extract_usage_metadata(response),
        turn_number=state.get("turn_number"),
    )
    state["story_memory"] = _dump_model(parsed.story_memory)
    save_session(session_id, state)


@router.post("/turn")
def next_turn(payload: TurnRequest, background_tasks: BackgroundTasks) -> dict:
    record = get_session(payload.session_id)
    if record is None:
        return JSONResponse(
            status_code=404,
            content={"error_type": "SESSION_NOT_FOUND", "message": "Invalid session_id."},
        )

    state = record.state_json
    previous_scenes = state.get("previous_scenes", [])
    if not previous_scenes:
        return JSONResponse(
            status_code=400,
            content={"error_type": "INVALID_STATE", "message": "No previous scenes found."},
        )

    # Update the last scene with the player's selected action
    previous_scenes[-1]["selected_action"] = payload.action

    story_memory = state.get("story_memory")
    if story_memory:
        recent_scenes = previous_scenes[-3:]
    else:
        recent_scenes = previous_scenes

    next_turn_number = state.get("turn_number", 1) + 1
    state["turn_number"] = next_turn_number

    state_for_context = dict(state)
    state_for_context["turn_number"] = next_turn_number

    dynamic_context = _build_dynamic_context(state_for_context, recent_scenes)

    client = get_genai_client()
    response = client.models.generate_content(
        model="gemini-3-flash-preview",
        config=types.GenerateContentConfig(
            system_instruction=STATIC_PROMPT,
            response_mime_type="application/json",
            response_json_schema=DirectorNarratorOutput.model_json_schema(),
            thinking_config=get_thinking_config(),
        ),
        contents=dynamic_context,
    )

    try:
        parsed = validate_model_json(response.text, DirectorNarratorOutput)
    except StructuredOutputValidationError as exc:
        return JSONResponse(status_code=422, content=exc.to_error_payload())
    record_token_usage(
        state,
        "director",
        extract_usage_metadata(response),
        turn_number=next_turn_number,
    )

    prior_inventory = {
        item["name"]: item.get("new_count", 0)
        for item in state.get("inventory", [])
    }
    prior_skills = {
        (skill["domain"], skill["name"]): skill.get("value", 0)
        for skill in state.get("skills", [])
    }

    # Apply inventory + skill changes deterministically
    updated_inventory, failed_inventory = _apply_inventory_changes(state, parsed.inventory_changes)
    updated_skills, failed_skill = _apply_skill_change(state, parsed.skill_change)

    # If failures, run canonicalizer and retry
    if failed_inventory or failed_skill is not None:
        canonical_inventory = [item["name"] for item in state.get("inventory", [])]
        canonical_skills_by_domain: Dict[str, List[str]] = {}
        for skill in state.get("skills", []):
            canonical_skills_by_domain.setdefault(skill["domain"], []).append(skill["name"])

        canonical_out, canonicalizer_usage = _run_canonicalizer(
            canonical_inventory=canonical_inventory,
            canonical_skills_by_domain=canonical_skills_by_domain,
            failed_inventory_updates=failed_inventory,
            failed_skill_update=failed_skill,
            scene_excerpt=parsed.next_scene.text_story[:300],
            player_action=payload.action,
        )
        record_token_usage(
            state,
            "canonicalizer",
            canonicalizer_usage,
            turn_number=next_turn_number,
        )

        # Retry applying corrected updates
        updated_inventory, _ = _apply_inventory_changes(
            state,
            canonical_out.corrected_inventory_updates,
        )
        updated_skills, _ = _apply_skill_change(
            state,
            canonical_out.corrected_skill_update,
        )

    state["inventory"] = updated_inventory
    state["skills"] = updated_skills

    updated_inventory_map = {item["name"]: item for item in updated_inventory}
    updated_counts = {name: item.get("new_count", 0) for name, item in updated_inventory_map.items()}
    inventory_delta_this_turn: list[dict[str, Any]] = []
    for name in sorted(set(prior_inventory) | set(updated_counts)):
        previous_count = prior_inventory.get(name, 0)
        new_count = updated_counts.get(name, 0)
        if previous_count == new_count:
            continue

        if previous_count == 0 and new_count > 0:
            change_type = "NEW"
        elif new_count > previous_count:
            change_type = "INCREASED"
        elif new_count == 0 and previous_count > 0:
            change_type = "REMOVED"
        else:
            change_type = "DECREASED"

        inventory_item = updated_inventory_map.get(name, {})
        inventory_delta_this_turn.append(
            {
                "name": name,
                "previous_count": previous_count,
                "new_count": new_count,
                "change_type": change_type,
                "reason": inventory_item.get("reason"),
                "note": inventory_item.get("note"),
            }
        )

    if parsed.next_scene.music_action == "CHANGE" and parsed.next_scene.music_prompt:
        state["current_music"] = parsed.next_scene.music_prompt

    # Generate media in parallel
    session_slug = _session_slug(payload.session_id)
    media_paths: Dict[str, Optional[str]] = {"image_path": None, "tts_path": None, "music_path": None}
    try:
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures: Dict[str, Any] = {}
            if parsed.next_scene.media_type == "image":
                futures["image_path"] = executor.submit(
                    generate_scene_image,
                    parsed.next_scene.media_prompt,
                    f"{session_slug}_scene_{next_turn_number}.png",
                )
            futures["tts_path"] = executor.submit(
                generate_tts,
                parsed.next_scene.text_story,
                f"{session_slug}_tts_{next_turn_number}.wav",
            )
            if parsed.next_scene.music_action == "CHANGE" and parsed.next_scene.music_prompt:
                futures["music_path"] = executor.submit(
                    generate_music,
                    parsed.next_scene.music_prompt,
                    f"{session_slug}_music_{next_turn_number}.wav",
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

    # Append the newly generated scene with no selected action yet
    previous_scenes.append(
        {
            "number_of_scene": next_turn_number,
            "text_story": parsed.next_scene.text_story,
            "selected_action": None,
            "media": {
                "media_type": parsed.next_scene.media_type,
                "image_path": media_paths["image_path"],
                "tts_path": media_paths["tts_path"],
                "music_path": media_paths["music_path"],
            },
        }
    )
    state["previous_scenes"] = previous_scenes

    save_session(payload.session_id, state)

    if next_turn_number == 13:
        background_tasks.add_task(_summarize_story_memory, payload.session_id)

    return {
        "session_id": payload.session_id,
        "turn_number": next_turn_number,
        "scene": {
            "text_story": parsed.next_scene.text_story,
            "action_options": _dump_model(parsed.next_scene).get("action_options", []),
            "media_type": parsed.next_scene.media_type,
            "media_prompt": parsed.next_scene.media_prompt,
            "image_path": media_paths["image_path"],
            "tts_path": media_paths["tts_path"],
            "music_action": parsed.next_scene.music_action,
            "music_prompt": parsed.next_scene.music_prompt,
            "music_path": media_paths["music_path"],
        },
        "hints": _dump_model(parsed.hints),
        "narrative_alignment": _dump_model(parsed.narrative_alignment),
        "is_game_over": parsed.is_game_over,
        "is_it_ending": parsed.is_it_ending,
        "director_output": _dump_model(parsed),
        "inventory": updated_inventory,
        "inventory_delta_this_turn": inventory_delta_this_turn,
        "skills": updated_skills,
        "skill_delta_this_turn": [
            {
                "domain": skill["domain"],
                "name": skill["name"],
                "previous_value": prior_skills.get((skill["domain"], skill["name"]), 0),
                "new_value": skill.get("value", 0),
                "delta": skill.get("value", 0) - prior_skills.get((skill["domain"], skill["name"]), 0),
            }
            for skill in updated_skills
            if skill.get("value", 0) != prior_skills.get((skill["domain"], skill["name"]), 0)
        ],
        "current_music": state.get("current_music"),
        "simulation_metrics": state.get("token_usage", {}),
    }
