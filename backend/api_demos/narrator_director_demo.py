# backend/api_demos/narrator_director_demo.py

from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT_DIR))
import json
from typing import Any, Dict, List, Optional, Literal

from google.genai import types

from backend.clients import get_genai_client, get_thinking_config
from backend.prompts.narrator_director import STATIC_PROMPT
from backend.schemas import DirectorNarratorOutput


# =========================================
# HARD CODED INPUT TO TEST FIRST DIRECTOR CALL
# =========================================
# Assumption for the very first Director call:
# - The player has just selected their first action from Scene 1
# - The Director must generate Scene 2
# - Inventory is empty at the beginning

NARRATIVE_DIRECTOR_FIRST_CALL_CONTEXT = {
  "main_dramatic_concept": "The burden of forgotten sins.",
  "core_plot": (
    "The player is Elias Thorne, an elite cleaner for a global syndicate who voluntarily underwent a memory wipe "
    "to escape his contract. This jazz club, The Velvet Void, serves as the designated point for his final handler "
    "to either confirm his successful exit or execute him if he still possesses classified information. The tension "
    "is built on the fact that while the player has forgotten his identity, the enemies and allies in the room have not, "
    "and they are waiting for a specific behavioral cue to determine if he is a threat or a blank slate. Resolution will "
    "occur when the syndicate's local Enforcer arrives to test the player's reflexes and memory through a high-stakes interrogation."
  ),
  "anchor_events": [
    {"event": "The confrontation with the past."},
    {"event": "The opening of the locked case."},
    {"event": "The arrival of the final extraction."}
  ],
  "endings": [
    {"ending": "The player regains their memories and returns to their life as a lethal operative."},
    {"ending": "The player successfully fakes their identity and disappears into a new, quiet life."},
    {"ending": "The player is eliminated by the syndicate as a loose end."},
    {"ending": "The player exposes the syndicate to the authorities, choosing a life in witness protection."}
  ],

  # No story_memory early on
  "story_memory": None,

  # For early turns, recent_scenes == previous_scenes
  "recent_scenes": [
    {
      "number_of_scene": 1,
      "text_story": (
        "The air in The Velvet Void is thick with tobacco smoke and the dying notes of a saxophone. "
        "You are nursing a bourbon you do not remember ordering. Suddenly, the music stops with the sharp, ugly screech "
        "of a needle pulled across vinyl. The silence is heavy. At the bar, a man in a charcoal suit freezes, his eyes "
        "widening in the mirror. He turns, his voice a trembling whisper that cuts through the quiet: 'Thorne? They said "
        "you were dead in Geneva.' Around the room, hands drift toward coat pockets and shadows shift toward the exits. "
        "Your mind is a total blank, but your pulse remains unnervingly slow. You have no idea who Thorne is, but every "
        "person in this room is looking at you like a ghost."
      ),
      "selected_action": "I scan the room to identify every possible exit and immediate threat."
    }
  ],

  "current_music": "Dark noir jazz, slow and tense upright bass, occasional distant police siren, atmospheric silence.",
  "skills": [
    {"domain": "SENSE", "name": "Observation", "value": 0, "explanation": "Detect details, read body language, notice hazards. Not social manipulation."},
    {"domain": "TALK", "name": "Influence", "value": 0, "explanation": "Persuade, deceive, intimidate via speech. Not physical action."},
    {"domain": "MOVE", "name": "Coordination", "value": 0, "explanation": "Move quickly, dodge, maintain stealth. Not tool use."},
    {"domain": "MAKE", "name": "Ingenuity", "value": 0, "explanation": "Use tools, modify environment, improvise solutions. Not direct combat."},
    {"domain": "ENDURE", "name": "Resilience", "value": 0, "explanation": "Withstand pressure, fear, pain. Not external movement."}
  ],
  "inventory": [],  # no inventory yet

  "game_length_mode": "SHORT",  # "SHORT" | "LONG" | "INFINITE"
  "target_turns_hint": 10,      # 10 for SHORT, 20 for LONG, None for INFINITE
  "turn_number": 2  # generating Scene 2 after the player's first action
}



# =========================================
# DIRECTOR NARRATOR PROMPT (STATIC + DYNAMIC)
# =========================================
# Cache STATIC_PROMPT. Append DYNAMIC_CONTEXT at runtime.



def build_dynamic_context(context: Dict[str, Any]) -> str:
    """
    Builds a single text payload to pass as `contents` to the Director model call.

    Expected keys in context:
      main_dramatic_concept: str
      core_plot: str
      anchor_events: list[dict]
      endings: list[dict]
      story_memory: Optional[str]   (summary of older scenes, can be "" early game)
      recent_scenes: list[dict]     (last 3 scenes max, each includes number_of_scene, text_story, selected_action)
      current_music: str
      skills: list[dict]
      inventory: list[dict]
      game_length_mode: str
      target_turns_hint: Optional[int]
      turn_number: int
    """

    story_memory = context.get("story_memory") or ""
    recent_scenes: List[Dict[str, Any]] = context.get("recent_scenes") or []

    payload = {
        "main_dramatic_concept": context["main_dramatic_concept"],
        "core_plot": context["core_plot"],
        "anchor_events": context["anchor_events"],
        "endings": context["endings"],

        "story_memory": story_memory,          # summary of earlier turns (can be empty)
        "recent_scenes": recent_scenes,        # last 3 scenes only

        "current_music": context["current_music"],
        "skills": context["skills"],
        "inventory": context["inventory"],
        "game_length_mode": context["game_length_mode"],
        "target_turns_hint": context.get("target_turns_hint", None),
        "turn_number": context["turn_number"],
    }

    return (
        "DYNAMIC CONTEXT (internal, do not repeat back to the player)\n"
        + json.dumps(payload, ensure_ascii=False, indent=2)
    )


# =========================================
# CALL EXAMPLE (FIRST DIRECTOR CALL)
# =========================================

client = get_genai_client()

dynamic_context = build_dynamic_context(NARRATIVE_DIRECTOR_FIRST_CALL_CONTEXT)

response = client.models.generate_content(
    model="gemini-3-flash-preview",
    config=types.GenerateContentConfig(
        system_instruction=STATIC_PROMPT,
        response_mime_type="application/json",
        response_json_schema=DirectorNarratorOutput.model_json_schema(),
        thinking_config=get_thinking_config(),  # "high" for production
    ),
    contents=dynamic_context,
)

# ---------
# Outputs
# ---------

# Print Tokens
usage = response.usage_metadata
print(f"Input Tokens:    {usage.prompt_token_count}")
print(f"Thinking Tokens: {usage.thoughts_token_count}")
print(f"Output Tokens:   {usage.candidates_token_count}")
print(f"--------------------------")
print(f"Total Tokens:    {usage.total_token_count}")

# Print JSON Response

director_out = DirectorNarratorOutput.model_validate_json(response.text)
print(json.dumps(director_out.model_dump(), indent=2, ensure_ascii=False))
