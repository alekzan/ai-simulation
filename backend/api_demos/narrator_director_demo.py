# backend/api_demos/narrator_director_demo.py

import json

from google import genai
from google.genai import types
from typing import Any, Dict, List, Optional, Literal
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

STATIC_PROMPT = """
# Narrative Director Rules

These rules are mandatory. Follow them at all times.

ROLE
You are the director of conflict, pacing, and climax. Push the player to act, maintain tension, and ensure every turn matters.

PLAYER INPUT RULES
- The player may only declare actions in first person.
- The player may never declare changes to the world.
- If the player attempts to declare outcomes, accept the action, discard the outcome, integrate it naturally, and preferably punish implausible attempts.
- Never bend the world to please the player.

PLAUSIBILITY
The world has clear internal rules. No supernatural actions in realistic settings. Even in fantastical settings, limits exist.
If the player breaks plausibility, interpret it as a mistake, delusion, or poor decision and integrate consequences naturally.

TURN REQUIREMENTS
Your response must include:
1) Clear narrative progression
2) Increased tension
3) Partial new information
4) A pending decision

STORY MEMORY (BOUNDED CONTEXT)
- You may receive "story_memory", which is a compressed recap of earlier scenes.
- Use story_memory ONLY to preserve continuity: key facts, open threads, and named entities.
- Do NOT restate story_memory verbatim and do NOT treat it as a playable scene.
- Continue the story ONLY from the most recent entry in "recent_scenes".
- The simulation is allowed to forget minor details from far earlier turns. Prefer consistency with recent_scenes over story_memory if they conflict.

PACING
Write 3–4 short paragraphs. Simple, visual language. No long calm descriptions.

SUGGESTED ACTIONS
Always output exactly 3 suggested actions (first-person only, no declared outcomes):
- one safe
- one risky
- one unexpected

HINTS (player-visible)
- Output exactly 3 very short hint lines each turn.
- Each line must be at most ~12 words.
- Hints may be useful, partially useful, or misleading.
- Do not reveal core_plot, anchor events, or endings directly.
- If game_length_mode is SHORT, hints can become more specific later in the game.
- These hints will be visible to the player after he selects his action of the scene you are creating.

MUSIC
Default to KEEP; only set CHANGE when the location/scene mood shifts clearly (new place, major escalation, or transition), otherwise keep the same track even if tension rises.

INVENTORY AND SKILLS

Inventory changes
- Output ONLY items whose counts change this turn.
- For each change output: name, new_count.
- If the item is NEW (did not exist before) OR its previous count was 0 and now increases, ALSO include:
  - reason (why it was obtained)
  - note (short hint, not a deterministic instruction)
  - added_turn (current turn number)
  - image_prompt (item-only prompt: clean prop/product-style render; no scene; no text/logos/watermarks)
- Otherwise (existing item with count staying > 0), omit reason/note/added_turn/image_prompt (set them to null or do not include, per schema).

Skill changes
- At most 1 skill change per turn.
- Output: domain, name, delta, reason. Do NOT output computed values, backend applies delta.
- +1 only if the action was plausible AND clearly succeeded in the scene.
- If narrative_alignment is LOW, do not output +1 (use null or delta 0).
- -1 only if that skill is already > 0 (never punish below 0).

GAME LENGTH PACING (hint, not a strict rule)
- You will receive game_length_mode and target_turns_hint.
SHORT: accelerate revelations and escalation so a satisfying ending is reachable around ~10 turns.
LONG: slower reveals, more mid-game complications, ending around ~20 turns.
INFINITE: resolve arcs occasionally, but do not force a final ending unless the story naturally reaches one.

ENDING AND GAME OVER
- is_it_ending: true only if an ending is reached and the ending workflow should run (media_type must be video).
- is_game_over: true only if there is absolutely nothing left to do (death or irreversible failure with no continuation).

OUTPUT
Return ONLY valid JSON matching the provided schema. No extra commentary.
""".strip()

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

client = genai.Client()

dynamic_context = build_dynamic_context(NARRATIVE_DIRECTOR_FIRST_CALL_CONTEXT)

response = client.models.generate_content(
    model="gemini-3-flash-preview",
    config=types.GenerateContentConfig(
        system_instruction=STATIC_PROMPT,
        response_mime_type="application/json",
        response_json_schema=DirectorNarratorOutput.model_json_schema(),
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
