# backend/api_demos/state_canonicalizer_demo.py
#
# Demo: "State Canonicalizer" (fallback AI call)
# Used ONLY when deterministic backend logic fails to apply an inventory/skill update
# because the Director output contains non-canonical names (e.g., "Knife" vs "Large knife").

import json
from typing import Any, Dict, List, Optional

from google import genai
from google.genai import types
from pydantic import BaseModel, Field
from typing import Literal


# Example import line (from any backend module)
from backend.schemas import FailedInventoryUpdate, FailedSkillUpdate, CanonicalizerInput, CanonicalizerOutput


# =========================
# Canonicalizer system prompt
# =========================

STATE_CANONICALIZER_SYSTEM = """
You are the State Canonicalizer.

You are called ONLY when the backend failed to apply a state update because a name did not match the canonical state.

GOAL
Given:
- canonical inventory names
- canonical skill names by domain
- the failed updates (inventory and/or skill)
Return the same updates but corrected so that their names match the canonical state.

STRICT RULES
- Output ONLY valid JSON matching the provided schema. No commentary.
- Do NOT change counts, deltas, new_value, reasons, or other fields unless required for schema validity.
- Your job is name canonicalization only.

MATCHING RULES
Inventory:
- If a failed inventory update looks like it references an existing item (example: reason/note are null, or it is a decrement or a change),
  then its name MUST be replaced with a canonical inventory name.
- Match using:
  1) exact match
  2) case-insensitive match
  3) singular/plural normalization and punctuation normalization
  4) semantic match ONLY if unambiguous
- If ambiguous, choose the safest best match and add a warning explaining ambiguity.

New item exception:
- If the update clearly introduces a NEW item (reason or note present AND the item is not in canonical list),
  you may keep it unchanged. Add no fix unless you are confident it is a renamed existing item.

Skills:
- If a failed skill update is provided, its name MUST be replaced with a canonical skill name within the same domain.
- Match using exact, case-insensitive, normalization, then semantic match.
- If ambiguous, keep the original and add a warning.

CONTEXT
- Only use scene_excerpt and player_action if provided, and only to break ties.
- If context is not provided, resolve strictly using the canonical lists.
""".strip()



client = genai.Client()

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
        image_prompt=None,
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
