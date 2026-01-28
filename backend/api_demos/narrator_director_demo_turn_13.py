# backend/api_demos/narrator_director_demo.py
# NARRATOR DIRECTOR 13th turn example
import json

from google import genai
from google.genai import types
from typing import Any, Dict, List, Optional, Literal
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

dynamic_context = build_dynamic_context(NARRATIVE_DIRECTOR_TURN_13_CONTEXT)

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
