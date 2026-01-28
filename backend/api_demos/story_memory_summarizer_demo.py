# AI Summarizer
# backend/api_demos/story_memory_summarizer_demo.py
#
# Demo: Story Memory Summarizer (bounded, structured)
# Purpose: Summarize scenes 1..K into a compact "story_memory" object to reduce tokens
#          for the Narrator Director call.
#
# NOTE: This demo is intentionally simple and hard-coded to teach the API usage pattern.

from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT_DIR))
import json
from typing import List, Optional, Literal

from pydantic import BaseModel, Field
from google.genai import types

from backend.clients import get_genai_client, get_thinking_config
from backend.prompts.story_memory_summarizer import SYSTEM_INSTRUCTION
from backend.schemas import StoryMemorySummarizerInput, StoryMemorySummarizerOutput



# ===========================================================================
# DEMO INPUT
# ===========================================================================

DEMO_INPUT = {
    "main_dramatic_concept": "The burden of forgotten sins.",
    "core_plot": (
        "The player is Elias Thorne, an elite cleaner for a global syndicate who voluntarily underwent a memory wipe "
        "to escape his contract. The Velvet Void is a checkpoint where a handler will confirm his exit or execute him "
        "if he still retains classified information. The room is a test: allies and enemies watch for cues that reveal "
        "whether he is still dangerous. Resolution builds toward an enforcer arriving to interrogate and force a choice."
    ),
    "anchor_events": [
        {"event": "The confrontation with the past."},
        {"event": "The opening of the locked case."},
        {"event": "The arrival of the final extraction."},
    ],
    "endings": [
        {"ending": "Regains memories and returns as a lethal operative."},
        {"ending": "Fakes identity and disappears into a new life."},
        {"ending": "Eliminated by the syndicate as a loose end."},
        {"ending": "Exposes syndicate, enters witness protection."},
    ],
    "scenes_to_summarize": [
        {
            "number_of_scene": 1,
            "text_story": "The music dies in The Velvet Void as someone recognizes you as Thorne. Hands drift to pockets. You have no memory, but the room does.",
            "selected_action": "I scan the room to identify every possible exit and immediate threat.",
        },
        {
            "number_of_scene": 2,
            "text_story": "You clock the exits and the people who block them. A bartender watches you too closely. A man in a back booth signals once, then goes still.",
            "selected_action": "I keep my face calm and ask the bartender what ‘Geneva’ means to them.",
        },
        {
            "number_of_scene": 3,
            "text_story": "The bartender answers around the truth. A locked case under the bar becomes obvious once you notice the bartender’s protective posture.",
            "selected_action": "I subtly angle for a look at what’s under the bar without reaching for it.",
        },
                {
            "number_of_scene": 4,
            "text_story": "A woman at the piano stops mid-note and watches you like she’s counting breaths. The back booth watcher shifts, and a cigarette ember brightens as if someone just received a signal. Behind the bar, the locked case is moved an inch, then held still, like a dare.",
            "selected_action": "I mirror the room’s stillness and try to catch who just signaled to the outside.",
        },
        {
            "number_of_scene": 5,
            "text_story": "The bartender slides your glass away, then back, testing your reaction. A faint buzz in the wall phone near the kitchen door suggests a call that never fully rings. Two men by the side exit angle their bodies to close the gap without stepping forward.",
            "selected_action": "I speak softly to the bartender and ask who would benefit most if the case never opened.",
        },
        {
            "number_of_scene": 6,
            "text_story": "The booth watcher finally meets your eyes, just once, then looks past you to the door as if timing something. Outside, tires hiss on wet pavement. Inside, the sax player wets his reed but doesn’t play, waiting for permission that isn’t coming.",
            "selected_action": "I reposition one step to put the bar between me and the side exit without making it obvious.",
        },
        {
            "number_of_scene": 7,
            "text_story": "A match strikes. The piano woman leans close to someone you can’t see clearly, and you catch a single word: “extract.” The bartender’s knuckles whiten on the counter. The locked case feels less like an object and more like an appointment.",
            "selected_action": "I ask the piano woman if she knows the name Thorne, and I watch her hands while she answers.",
        },
        {
            "number_of_scene": 8,
            "text_story": "Your question pulls attention like a magnet. The room tightens. The booth watcher’s shoe taps twice, then stops. A faint metallic click comes from under the bar, subtle enough to deny, loud enough to warn.",
            "selected_action": "I keep my voice calm and say I’m here for the truth, not a fight, then wait to see who flinches.",
        },
        {
            "number_of_scene": 9,
            "text_story": "For a heartbeat, nobody moves. Then the bartender slides a napkin toward you with a greasy smudge that could be numbers or a stain pretending to be one. The side-exit men don’t touch you, but they’re close enough now that you’d feel it if they did.",
            "selected_action": "I take the napkin without looking down, and I ask who’s on the other end of the updates outside.",
        },
        {
            "number_of_scene": 10,
            "text_story": "You keep your eyes up as you pocket the napkin, letting the room believe you already know what it says. The bartender doesn’t answer, but his gaze flicks once to the wall phone by the kitchen door. The back booth watcher shifts again, not toward you, but toward the entrance, like the next beat is scheduled. A soft knock comes from outside, not the kind a customer uses. The locked case seems to pull the silence toward it, as if whatever’s inside is about to become the only thing that matters.",
            "selected_action": "I stay still, listen for a second knock, and angle my body so I can see the entrance and the case at the same time.",
        },

    ],
    # Optional: include if you're updating instead of summarizing from scratch
    "current_story_memory": None,
}



client = get_genai_client()

parsed = StoryMemorySummarizerInput.model_validate(DEMO_INPUT)

response = client.models.generate_content(
    model="gemini-3-flash-preview",
    config=types.GenerateContentConfig(
        system_instruction=SYSTEM_INSTRUCTION,
        response_mime_type="application/json",
        response_json_schema=StoryMemorySummarizerOutput.model_json_schema(),
        thinking_config=get_thinking_config(),  # "high" for production
    ),
    contents=json.dumps(parsed.model_dump(), ensure_ascii=False),
)

# ---------
# Outputs
# ---------
usage = getattr(response, "usage_metadata", None)
if usage:
    print(f"Input Tokens:    {getattr(usage, 'prompt_token_count', 'n/a')}")
    print(f"Thinking Tokens: {getattr(usage, 'thoughts_token_count', 'n/a')}")
    print(f"Output Tokens:   {getattr(usage, 'candidates_token_count', 'n/a')}")
    print(f"--------------------------")
    print(f"Total Tokens:    {getattr(usage, 'total_token_count', 'n/a')}")

out = StoryMemorySummarizerOutput.model_validate_json(response.text)
print(json.dumps(out.model_dump(), indent=2, ensure_ascii=False))
