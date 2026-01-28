# backend/api_demos/narrator_director_demo.py
# NARRATOR DIRECTOR 13th turn example
import json
from typing import Any, Dict, List, Optional, Literal

from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT_DIR))
from google.genai import types

from backend.clients import get_genai_client, get_thinking_config
from backend.prompts.narrator_director import STATIC_PROMPT
from backend.schemas import DirectorNarratorOutput


# =========================================
# HARD CODED INPUT TO TEST FIRST DIRECTOR CALL
# =========================================
# Assumption for the 13th Director call:
# - The player has just selected their 13 action from Scene 13
# - The Director must generate Scene 14
# - Inventory and skills already have values.

NARRATIVE_DIRECTOR_TURN_13_CONTEXT = {
  "main_dramatic_concept": "The burden of forgotten sins.",
  "core_plot": (
    "The player is Elias Thorne, an elite cleaner for a global syndicate who voluntarily underwent a memory wipe "
    "to escape his contract. This jazz club, The Velvet Void, serves as the designated point for his final handler "
    "to either confirm his successful exit or execute him if he still possesses classified information..."
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

  # Bounded memory: this summary covers ONLY up to scene 9.
  # You can decide to refresh/overwrite it occasionally, but do not grow it forever.
  "story_memory": {
    "summary": (
      "You woke into The Velvet Void with no memory and the room reacting to the name Thorne. "
      "You mapped exits, bluffed through probing questions, and uncovered hints of a syndicate test designed to confirm whether you’re a threat or a blank slate. "
      "A locked case became the focal point, with multiple players circling it: a bartender who knows too much, a watcher in the back booth, and a handler who keeps moving the goalposts."
    ),
    "key_facts": [
      "The syndicate is testing whether you still retain operational memory.",
      "A locked case exists and is important, but its contents are still uncertain.",
      "At least one person in the bar is feeding information to someone outside."
    ],
    "open_threads": [
      "What is inside the locked case and why does it matter to your erased identity?",
      "Who is the real handler: the bartender, the watcher, or someone unseen?",
      "Is the incoming enforcer here to extract you or erase you?"
    ],
    "known_entities": [
      {"name": "The Velvet Void", "type": "location", "note": "Noir jazz bar used as a syndicate checkpoint."},
      {"name": "Locked Case", "type": "object", "note": "Heavily protected, draws attention, likely contains leverage or identity proof."},
      {"name": "Back Booth Watcher", "type": "npc", "note": "Observes silently, signals at key moments."}
    ],
    "last_summarized_scene": 10
  },

  # Keep the last 3 scenes verbatim for continuity (10, 11, 12),
  # and the Director continues from the MOST RECENT one.
  "recent_scenes": [
    {
      "number_of_scene": 11,
      "text_story": (
        "A power flicker ripples through the bar, and for a heartbeat the neon dies. "
        "When it returns, the bartender’s hand is already under the counter. "
        "The back booth watcher taps ash into a glass, slow, deliberate, like a metronome."
      ),
      "selected_action": "I keep my hands visible and watch the bartender’s shoulders for the first sign of movement."
    },
    {
      "number_of_scene": 12,
      "text_story": (
        "The bartender slides a coaster toward you. Under it, a thin paper keycode, smudged like it’s been handled too many times. "
        "A low voice from the booth: 'Wrong answer, and the case never opens.' "
        "Outside, a car door shuts. The sound is clean, confident."
      ),
      "selected_action": "I pocket the keycode without looking down and try to catch who’s watching me react."
    },
    {
      "number_of_scene": 13,
      "text_story": (
        "The entrance bell gives a soft ring. A man steps in with rain on his shoulders and no hurry in his stride. "
        "He doesn’t scan the room. He already knows where everyone is. His eyes find you like a signature. "
        "He nods once, as if confirming a suspicion, and says, 'Let’s see what’s left in you.'"
      ),
      "selected_action": "I hold eye contact and say, 'Tell me what you think I did in Geneva.'"
    }
  ],

  "current_music": "Noir jazz with a thin, tense pulse, upright bass, brushed snare, faint room tone.",
  "skills": [
    {"domain": "SENSE", "name": "Observation", "value": 2, "explanation": "Detect details, read body language, notice hazards. Not social manipulation."},
    {"domain": "TALK", "name": "Influence", "value": 1, "explanation": "Persuade, deceive, intimidate via speech. Not physical action."},
    {"domain": "MOVE", "name": "Coordination", "value": 1, "explanation": "Move quickly, dodge, maintain stealth. Not tool use."},
    {"domain": "MAKE", "name": "Ingenuity", "value": 0, "explanation": "Use tools, modify environment, improvise solutions. Not direct combat."},
    {"domain": "ENDURE", "name": "Resilience", "value": 1, "explanation": "Withstand pressure, fear, pain. Not external movement."}
  ],
  "inventory": [
    {"name": "Keycode Slip", "count": 1, "note": "Smudged paper code taken from bartender."},
    {"name": "Matchbook", "count": 1, "note": "From the bar, back cover has an address."}
  ],

  "game_length_mode": "LONG",
  "target_turns_hint": 20,
  "turn_number": 14
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

dynamic_context = build_dynamic_context(NARRATIVE_DIRECTOR_TURN_13_CONTEXT)

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
