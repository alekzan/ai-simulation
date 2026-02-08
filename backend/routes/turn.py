from __future__ import annotations

import json
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, Request
from fastapi.responses import JSONResponse
from google.genai import types
from pydantic import BaseModel

from backend.clients import get_genai_client, get_thinking_config
from backend.db import get_session, save_session
from backend.ephemeral_media import (
    EPHEMERAL_IMAGE_TTL_SECONDS,
    EPHEMERAL_MUSIC_TTL_SECONDS,
    EPHEMERAL_TTS_TTL_SECONDS,
    build_ephemeral_path,
    prune_expired_media,
    store_media,
)
from backend.media import (
    cleanup_expired_media,
    delete_media_files,
    generate_ending_video,
    generate_music_bytes,
    generate_scene_image,
    generate_scene_image_bytes,
    generate_tts_bytes,
)
from backend.prompts.narrator_director import STATIC_PROMPT
from backend.request_auth import get_request_api_key, missing_api_key_response
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


def _last_music_path(previous_scenes: list[dict]) -> Optional[str]:
    for scene in reversed(previous_scenes):
        media = scene.get("media", {})
        path = media.get("music_path")
        if path:
            return path
    return None


def _prune_old_scene_media(
    previous_scenes: list[dict],
    keep_last: int,
    keep_music_path: Optional[str],
) -> None:
    if keep_last <= 0 or len(previous_scenes) <= keep_last:
        return
    for scene in previous_scenes[:-keep_last]:
        media = scene.get("media", {})
        for key in ("image_path", "tts_path", "video_path", "music_path"):
            path = media.get(key)
            if not path:
                continue
            if key == "music_path" and keep_music_path and path == keep_music_path:
                continue
            delete_media_files([path])
            media[key] = None


def _is_development_mode() -> bool:
    env = os.getenv("APP_ENV", "development").strip().lower()
    return env not in {"production", "prod"}


def _extract_debug_action(raw_action: str) -> tuple[str, bool, bool]:
    if not _is_development_mode():
        return raw_action, False, False

    ending_token = os.getenv("ENDING_DEBUG_TOKEN", "3nD1n6N0W").strip()
    gameover_token = os.getenv("GAMEOVER_DEBUG_TOKEN", "G4m30v3rN0W").strip()

    force_ending = bool(ending_token and ending_token in raw_action)
    force_game_over = bool(gameover_token and gameover_token in raw_action)
    if not force_ending and not force_game_over:
        return raw_action, False, False

    cleaned_action = raw_action
    if force_ending:
        cleaned_action = cleaned_action.replace(ending_token, "")
    if force_game_over:
        cleaned_action = cleaned_action.replace(gameover_token, "")
    cleaned_action = cleaned_action.strip()
    if not cleaned_action:
        cleaned_action = "I trigger the emergency ending protocol."
    return cleaned_action, force_ending, force_game_over


def _force_ending_output(parsed: DirectorNarratorOutput) -> None:
    parsed.is_it_ending = True
    parsed.is_game_over = True
    parsed.next_scene.media_type = "video"
    parsed.next_scene.action_options = []
    if not parsed.next_scene.ending_image_prompt:
        parsed.next_scene.ending_image_prompt = parsed.next_scene.media_prompt
    if not parsed.next_scene.ending_video_prompt:
        parsed.next_scene.ending_video_prompt = parsed.next_scene.media_prompt
    parsed.next_scene.text_story = (
        parsed.next_scene.text_story.rstrip()
        + "\n\nThe simulation enters terminal state. This run is complete."
    )


def _force_bad_game_over_output(parsed: DirectorNarratorOutput) -> None:
    parsed.is_it_ending = False
    parsed.is_game_over = True
    if parsed.next_scene.media_type == "video":
        parsed.next_scene.media_type = "image"
    parsed.next_scene.action_options = []
    parsed.next_scene.ending_image_prompt = None
    parsed.next_scene.ending_video_prompt = None


def _ensure_video_audio_cues(prompt: str) -> str:
    lowered = prompt.lower()
    if any(token in lowered for token in ("audio", "sound", "sfx", "ambience", "music", "score")):
        return prompt
    return (
        prompt.rstrip()
        + "\nAudio cues: low atmospheric wind, distant structural creaks, subtle rising cinematic score, "
        "final resonant impact at the conclusion."
    )


def _resolve_ending_prompts(next_scene) -> tuple[str, str]:
    base = (
        next_scene.ending_video_prompt
        or next_scene.ending_image_prompt
        or next_scene.media_prompt
        or "Cinematic final scene with strong continuity and no text overlays."
    ).strip()

    image_prompt = (next_scene.ending_image_prompt or base).strip()
    video_seed = (next_scene.ending_video_prompt or base).strip()
    video_prompt = _ensure_video_audio_cues(video_seed)
    return image_prompt, video_prompt


def _build_ending_video_prompt(text_story: str, video_prompt: str) -> str:
    return (
        "Create a cinematic ending video that faithfully visualizes the final scene narrative.\n"
        "Primary narrative source (must drive shot progression and story beats):\n"
        f"{text_story}\n\n"
        "Visual direction and style constraints:\n"
        f"{video_prompt}\n\n"
        "Requirements:\n"
        "- Continue naturally from the provided first frame image.\n"
        "- Keep the same characters, setting, tone, and physical consequences.\n"
        "- Resolve the ending clearly with a final beat, not a cliffhanger.\n"
        "- Show clear motion and escalation that feels like the ending beat.\n"
        "- No text, letters, logos, signage, subtitles, or UI overlays.\n"
    )


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
    api_key: str,
) -> tuple[CanonicalizerOutput, dict[str, int]]:
    client = get_genai_client(api_key=api_key)

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


def _summarize_story_memory(session_id: str, api_key: str) -> None:
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

    client = get_genai_client(api_key=api_key)
    try:
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
    except Exception:
        return

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
def next_turn(payload: TurnRequest, background_tasks: BackgroundTasks, request: Request) -> dict:
    api_key = get_request_api_key(request)
    if not api_key:
        return missing_api_key_response()
    cleanup_expired_media()
    prune_expired_media()

    record = get_session(payload.session_id)
    if record is None:
        return JSONResponse(
            status_code=404,
            content={"error_type": "SESSION_NOT_FOUND", "message": "Invalid session_id."},
        )

    state = record.state_json
    if state.get("is_game_over"):
        return JSONResponse(
            status_code=409,
            content={
                "error_type": "GAME_ALREADY_OVER",
                "message": "This session has ended. Reset to start a new simulation.",
            },
        )

    previous_scenes = state.get("previous_scenes", [])
    if not previous_scenes:
        return JSONResponse(
            status_code=400,
            content={"error_type": "INVALID_STATE", "message": "No previous scenes found."},
        )
    current_music_path = _last_music_path(previous_scenes)

    player_action, force_ending, force_bad_game_over = _extract_debug_action(payload.action)

    # Update the last scene with the player's selected action
    previous_scenes[-1]["selected_action"] = player_action

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
    if force_ending:
        dynamic_context += (
            "\n\nDEVELOPMENT OVERRIDE:\n"
            "The player used the debug ending token. You must finish the story now.\n"
            "- Set is_it_ending=true\n"
            "- Set is_game_over=true\n"
            "- Produce a final closing scene (no cliffhanger)\n"
            "- Set next_scene.media_type=video\n"
            "- Provide both next_scene.ending_image_prompt and next_scene.ending_video_prompt\n"
            "- ending_video_prompt must include explicit audio cues\n"
            "- Return no further action options\n"
        )
    elif force_bad_game_over:
        dynamic_context += (
            "\n\nDEVELOPMENT OVERRIDE:\n"
            "The player used the debug game-over token. You must end the run immediately WITHOUT ending video.\n"
            "- Set is_it_ending=false\n"
            "- Set is_game_over=true\n"
            "- Produce a terminal failure scene in current medium (prefer image)\n"
            "- Return no further action options\n"
        )

    client = get_genai_client(api_key=api_key)
    try:
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
    except Exception as exc:
        return JSONResponse(
            status_code=502,
            content={"error_type": "MODEL_CALL_FAILED", "message": str(exc)},
        )

    try:
        parsed = validate_model_json(response.text, DirectorNarratorOutput)
    except StructuredOutputValidationError as exc:
        return JSONResponse(status_code=422, content=exc.to_error_payload())
    if force_ending:
        _force_ending_output(parsed)
    elif force_bad_game_over:
        _force_bad_game_over_output(parsed)
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

        try:
            canonical_out, canonicalizer_usage = _run_canonicalizer(
                canonical_inventory=canonical_inventory,
                canonical_skills_by_domain=canonical_skills_by_domain,
                failed_inventory_updates=failed_inventory,
                failed_skill_update=failed_skill,
                scene_excerpt=parsed.next_scene.text_story[:300],
                player_action=player_action,
                api_key=api_key,
            )
        except Exception as exc:
            return JSONResponse(
                status_code=502,
                content={"error_type": "MODEL_CALL_FAILED", "message": str(exc)},
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

    scene_media_type = "video" if parsed.is_it_ending else parsed.next_scene.media_type
    if scene_media_type == "video":
        parsed.is_game_over = True
        parsed.next_scene.action_options = []
    if scene_media_type != "video" and parsed.next_scene.music_action == "CHANGE" and parsed.next_scene.music_prompt:
        state["current_music"] = parsed.next_scene.music_prompt

    ending_image_prompt: Optional[str] = None
    ending_video_prompt: Optional[str] = None
    if scene_media_type == "video":
        ending_image_prompt, ending_video_prompt = _resolve_ending_prompts(parsed.next_scene)
        parsed.next_scene.ending_image_prompt = ending_image_prompt
        parsed.next_scene.ending_video_prompt = ending_video_prompt

    state["is_game_over"] = bool(parsed.is_game_over)
    response_action_options = (
        [] if parsed.is_game_over or scene_media_type == "video" else _dump_model(parsed.next_scene).get("action_options", [])
    )

    # Generate media in parallel
    media_paths: Dict[str, Optional[str]] = {
        "image_path": None,
        "video_path": None,
        "tts_path": None,
        "music_path": None,
    }
    try:
        if scene_media_type == "video":
            session_slug = _session_slug(payload.session_id)
            ending_frame_path = generate_scene_image(
                ending_image_prompt or parsed.next_scene.media_prompt,
                f"{session_slug}_ending_frame_{next_turn_number}.png",
                api_key=api_key,
            )
            ending_prompt = _build_ending_video_prompt(
                parsed.next_scene.text_story,
                ending_video_prompt or parsed.next_scene.media_prompt,
            )
            video_path = generate_ending_video(
                ending_prompt,
                f"{session_slug}_ending_{next_turn_number}.mp4",
                Path(ending_frame_path),
                api_key=api_key,
            )
            delete_media_files([ending_frame_path])
            media_paths["video_path"] = str(video_path)
        else:
            with ThreadPoolExecutor(max_workers=3) as executor:
                futures: Dict[str, Any] = {}
                if scene_media_type == "image":
                    futures["image_path"] = executor.submit(
                        generate_scene_image_bytes,
                        parsed.next_scene.media_prompt,
                        api_key,
                    )
                futures["tts_path"] = executor.submit(
                    generate_tts_bytes,
                    parsed.next_scene.text_story,
                    api_key,
                )
                if parsed.next_scene.music_action == "CHANGE" and parsed.next_scene.music_prompt:
                    futures["music_path"] = executor.submit(
                        generate_music_bytes,
                        parsed.next_scene.music_prompt,
                        20,
                        api_key,
                    )

                for key, future in futures.items():
                    result = future.result()
                    if result is None:
                        media_paths[key] = None
                        continue
                    if key == "image_path":
                        image_bytes, image_mime = result
                        token = store_media(image_bytes, image_mime, EPHEMERAL_IMAGE_TTL_SECONDS)
                        media_paths[key] = build_ephemeral_path(token)
                    elif key == "tts_path":
                        token = store_media(result, "audio/wav", EPHEMERAL_TTS_TTL_SECONDS)
                        media_paths[key] = build_ephemeral_path(token)
                    elif key == "music_path":
                        token = store_media(result, "audio/wav", EPHEMERAL_MUSIC_TTL_SECONDS)
                        media_paths[key] = build_ephemeral_path(token)
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
                "media_type": scene_media_type,
                "image_path": media_paths["image_path"],
                "video_path": media_paths["video_path"],
                "tts_path": media_paths["tts_path"],
                "music_path": media_paths["music_path"],
            },
        }
    )
    keep_music_path = (
        media_paths["music_path"]
        if parsed.next_scene.music_action == "CHANGE" and media_paths["music_path"]
        else current_music_path
    )
    _prune_old_scene_media(previous_scenes, keep_last=1, keep_music_path=keep_music_path)
    state["previous_scenes"] = previous_scenes

    save_session(payload.session_id, state)

    if next_turn_number == 13 and not parsed.is_game_over:
        background_tasks.add_task(_summarize_story_memory, payload.session_id, api_key)

    return {
        "session_id": payload.session_id,
        "turn_number": next_turn_number,
        "scene": {
            "text_story": parsed.next_scene.text_story,
            "action_options": response_action_options,
            "media_type": scene_media_type,
            "media_prompt": parsed.next_scene.media_prompt,
            "image_path": media_paths["image_path"],
            "video_path": media_paths["video_path"],
            "tts_path": media_paths["tts_path"],
            "music_action": parsed.next_scene.music_action,
            "music_prompt": parsed.next_scene.music_prompt,
            "music_path": media_paths["music_path"],
            "ending_image_prompt": parsed.next_scene.ending_image_prompt,
            "ending_video_prompt": parsed.next_scene.ending_video_prompt,
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
