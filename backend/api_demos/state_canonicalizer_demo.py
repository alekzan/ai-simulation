# backend/api_demos/state_canonicalizer_demo.py
#
# Demo: "State Canonicalizer" (fallback AI call)
# Used ONLY when deterministic backend logic fails to apply an inventory/skill update
# because the Director output contains non-canonical names (e.g., "Knife" vs "Large knife").

from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT_DIR))
import json
from typing import Any, Dict, List, Optional

from google.genai import types
from pydantic import BaseModel, Field
from typing import Literal


# Example import line (from any backend module)
from backend.clients import get_genai_client, get_thinking_config
from backend.prompts.state_canonicalizer import STATE_CANONICALIZER_SYSTEM
from backend.schemas import FailedInventoryUpdate, FailedSkillUpdate, CanonicalizerInput, CanonicalizerOutput


client = get_genai_client()

# -------------------------
# Example: backend detected "key not found" for inventory + skill
# -------------------------

# Canonical state (what your backend currently stores)
canonical_inventory = ["Large knife", "Matchbook"]
canonical_skills_by_domain = {
    "SENSE": ["Observation"],
    "TALK": ["Influence"],
    "MOVE": ["Coordination"],
    "MAKE": ["Ingenuity"],
    "ENDURE": ["Resilience"],
}

# Failed updates (ONLY the ones that caused "not found" errors)
failed_inventory_updates = [
    FailedInventoryUpdate(
        name="Knife",          # wrong name
        new_count=1,           # director wants final count 1 (from 2 -> 1)
        reason=None,
        note=None,
        added_turn=None,
    )
]

failed_skill_update = FailedSkillUpdate(
    domain="MOVE",
    name="Coordination in battle",  # wrong name
    delta=-1,
    new_value=0,
    reason="You overcommitted and lost your footing.",
)

payload = CanonicalizerInput(
    canonical_inventory=canonical_inventory,
    canonical_skills_by_domain=canonical_skills_by_domain,
    failed_inventory_updates=failed_inventory_updates,
    failed_skill_update=failed_skill_update,
    # Optional disambiguation context (usually omit)
    scene_excerpt=None,
    player_action=None,
)

response = client.models.generate_content(
    model="gemini-3-flash-preview",
    config=types.GenerateContentConfig(
        system_instruction=STATE_CANONICALIZER_SYSTEM,
        response_mime_type="application/json",
        response_json_schema=CanonicalizerOutput.model_json_schema(),
        thinking_config=get_thinking_config(),  # "high" for production
    ),
    contents=json.dumps(payload.model_dump(), ensure_ascii=False),
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


out = CanonicalizerOutput.model_validate_json(response.text)

print(json.dumps(out.model_dump(), indent=2, ensure_ascii=False))

# -------------------------
# What your backend would do next (conceptually):
# - apply out.corrected_inventory_updates instead of the failed ones
# - apply out.corrected_skill_update instead of the failed one
# - log out.warnings for debugging
# -------------------------
