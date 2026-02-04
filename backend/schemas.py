# backend/schemas.py

"""
CENTRAL SCHEMAS MODULE

This file contains Pydantic models shared across scripts.

"""

from __future__ import annotations

from typing import Dict, List, Literal, Optional
from pydantic import BaseModel, Field



# ===========================================================================
# SCHEMA BLOCK: TITLE SCREEN SELECTOR (backend/title_screen_selector.py)
# ===========================================================================

# These schemas define the structured JSON output for the Title Screen Selector
# LLM call (3 title ideas + one-liner + cover image prompt).

class TitleIdea(BaseModel):
    id: Literal["A", "B", "C"] = Field(description="Stable identifier for UI selection.")
    title: str = Field(description="Short, catchy game title (2–6 words).")
    one_liner: str = Field(
        description=(
            "Single-line story hook. Must imply a problem/danger. No line breaks. "
            "Should clearly signal a specific genre/setting."
        )
    )
    cover_image_prompt: str = Field(
        description=(
            "Prompt for a premium cinematic poster image. Must specify style, mood, lighting, "
            "composition, key elements. Must include only the title text as readable typography. "
            "No logos, no watermarks, no taglines, no credits, no extra text, no UI."
        )
    )


class TitleScreenSelectorOutput(BaseModel):
    ideas: List[TitleIdea] = Field(
        description=(
            "Exactly 3 title ideas with title, one-liner, and cover image prompt. "
            "Ideas must be distinct in setting/genre."
        )
    )

# ===========================================================================
# SCHEMA BLOCK: INITIAL SCRIPT (backend/initial_script.py)
# ===========================================================================

# Shared schemas for action options + hints across outputs.

class ActionOption(BaseModel):
    action: str = Field(
        description="First-person action only. Must NOT declare world changes or outcomes."
    )


class Hint(BaseModel):
    text: str = Field(
        description="One very short hint line (max ~12 words). May be useful or not."
    )


class Hints(BaseModel):
    lines: List[Hint] = Field(
        description="Exactly 3 short hint lines."
    )


# These schemas define the structured JSON output for the Dramatic Architect
# initialization call: concept, internal plot spine, anchor events, endings,
# initial playable scene, and universal skills.

class AnchorEvent(BaseModel):
    event: str = Field(
        description="A short, inevitable event statement. Do not include how/when/who."
    )

class EndingType(BaseModel):
    ending: str = Field(
        description="A distinct ending type. Mutually exclusive vs others. No conditions."
    )

class InitialScene(BaseModel):
    text_story: str = Field(
        description="Initial scene narrative shown to the player. Must end with a pending decision."
    )
    image_prompt: str = Field(
        description="Prompt for a reference image matching the scene. No text, no logos, no watermarks, no letters, no numbers, no signage, no UI."
    )
    action_options: List[ActionOption] = Field(
        description="Exactly 3 suggested first-person actions."
    )
    music_prompt: str = Field(
        description="Instrumental background music prompt. No words, no lyrics."
    )

class Skill(BaseModel):
    domain: Literal["SENSE", "TALK", "MOVE", "MAKE", "ENDURE"] = Field(
        description="Skill domain bucket. Must be one of: SENSE, TALK, MOVE, MAKE, ENDURE."
    )
    name: str = Field(
        description="Short skill name. Must be universal and map clearly to the given domain."
    )
    value: int = Field(
        description="Skill value from 0 to 10. Must start at 0."
    )
    explanation: str = Field(
        description="Brief definition of what actions this skill covers, consistent with its domain."
    )

class InitialScriptOutput(BaseModel):
    main_dramatic_concept: str = Field(
        description="Single abstract concept that the story revolves around."
    )

    core_plot: str = Field(
        description=(
            "INTERNAL ONLY. A 1–2 paragraph causal narrative spine describing what is really going on, "
            "why the situation is tense, and what pressure will force resolution. "
        )
    )

    anchor_events: List["AnchorEvent"] = Field(
        description="2 or 3 important and inevitable events. Only the event statement."
    )

    endings: List["EndingType"] = Field(
        description="At least 4 distinct ending types. No conditions."
    )

    initial_scene: "InitialScene" = Field(
        description="Initial playable scene: text, image prompt, 3 actions, music prompt."
    )
    
    hints: Hints = Field(
        description="Exactly 3 short hint lines. Not mandatory for the player; can be misleading or vague."
    )

    skills: List["Skill"] = Field(
        description="Exactly 5 skills, all starting at 0/10 with explanations."
    )
    
    
# ===========================================================================
# SCHEMA BLOCK: NARRATIVE DIRECTOR (backend/narrator_director.py or similar)
# ===========================================================================

# These schemas define the structured JSON output for the Narrative Director call:
# next scene, inventory changes, skill change, narrative alignment, and ending flags.

class NextScene(BaseModel):
    text_story: str = Field(
        description="3–4 short paragraphs. Must increase tension, reveal partial new info, and end with a pending decision."
    )
    media_type: Literal["image", "video"] = Field(
        description="Use 'video' only if is_it_ending is true, otherwise 'image'."
    )
    media_prompt: str = Field(
        description="Prompt for the reference image (or ending video). No text, no logos, no watermarks, no letters, no numbers, no signage, no UI."
    )
    ending_image_prompt: Optional[str] = Field(
        default=None,
        description=(
            "Required when is_it_ending=true. Prompt for the generated first frame image of the ending video. "
            "Must match the same characters/location/style as ending_video_prompt. No text, no logos, no UI."
        ),
    )
    ending_video_prompt: Optional[str] = Field(
        default=None,
        description=(
            "Required when is_it_ending=true. Prompt for Veo continuation using the ending_image_prompt frame. "
            "Must conclude the final beat and include explicit audio cues (ambience, SFX, music/no music)."
        ),
    )
    action_options: List[ActionOption] = Field(
        description="Exactly 3 suggested first-person actions: one safe, one risky, one unexpected."
    )
    music_action: Literal["KEEP", "CHANGE"] = Field(
        description="Default KEEP. Use CHANGE only for a clear transition (new location/sequence) or major tonal shift."
    )
    music_prompt: Optional[str] = Field(
        default=None,
        description="Only if music_action=CHANGE. One concise instrumental prompt that matches the NEW mood; no words/lyrics."
    )
class InventoryChange(BaseModel):
    name: str = Field(description="Item name.")
    new_count: int = Field(description="Final count after this turn (0 means none).")
    reason: Optional[str] = Field(
        default=None,
        description="Why it was added. Only include when item count increases from 0 or the item is new."
    )
    note: Optional[str] = Field(
        default=None,
        description="Non-prescriptive hint about what the item is/why it matters. No instructions. Only include when new/increases from 0."
    )
    added_turn: Optional[int] = Field(
        default=None,
        description="Turn number when the item was first added. Only include when item count increases from 0 or the item is new."
    )

class SkillChange(BaseModel):
    domain: Literal["SENSE", "TALK", "MOVE", "MAKE", "ENDURE"] = Field(
        description="Skill domain bucket."
    )
    name: str = Field(description="Exact skill name from the provided skills list.")
    delta: Literal[-1, 0, 1] = Field(
        description="Change applied this turn. Must be -1, 0, or 1."
    )
    reason: Optional[str] = Field(
        default=None,
        description="One short line explaining why this skill changed."
    )


class NarrativeAlignment(BaseModel):
    value: Literal["HIGH", "MEDIUM", "LOW"] = Field(
        description="How well the player's action fits plausibility and dramatic direction. HIGH cooperates, MEDIUM resists with costs, LOW punishes."
    )

class DirectorNarratorOutput(BaseModel):
    next_scene: NextScene
    hints: Hints = Field(
        description="Exactly 3 very short hint lines for this turn. May be useful or not."
    )

    inventory_changes: List[InventoryChange] = Field(
        description="Only include items whose count changes this turn. Empty list if no inventory changes."
    )
    skill_change: Optional[SkillChange] = Field(
        description="At most 1 skill change per turn. If no change, set to null."
    )
    narrative_alignment: NarrativeAlignment
    is_game_over: bool = Field(
        description="True only if there is absolutely nothing left to do (e.g., death with no continuation)."
    )
    is_it_ending: bool = Field(
        description="True only if an ending is reached and the ending workflow should run (video). When true, next_scene must include ending_image_prompt and ending_video_prompt."
    )

# ===========================================================================
# SCHEMA BLOCK: STORY MEMORY SUMMARIZER (backend/story_memory_summarizer_demo.py)
# ===========================================================================
# Purpose: Summarize scenes 1..K into a compact "story_memory" object to reduce tokens
#          for the Narrator Director call.

class SceneToSummarize(BaseModel):
    number_of_scene: int = Field(description="Scene number in chronological order.")
    text_story: str = Field(description="Player-visible scene narrative.")
    selected_action: str = Field(description="The player's selected action for that scene.")


class KnownEntity(BaseModel):
    name: str = Field(description="Entity name, as it appears in the story.")
    type: Literal["npc", "location", "object", "faction", "other"] = Field(
        description="Entity category."
    )
    note: str = Field(description="One-line reminder of why it matters.")


class StoryMemory(BaseModel):
    summary: str = Field(
        description="Compact recap in 6–12 lines max. No bullets, no headings."
    )
    key_facts: List[str] = Field(
        description="Facts that must remain true. Short, declarative lines."
    )
    open_threads: List[str] = Field(
        description="Unresolved threads that should come back later."
    )
    known_entities: List[KnownEntity] = Field(
        description="Important NPCs/locations/objects/factions with one-line notes."
    )
    tone_style_notes: Optional[str] = Field(
        default=None,
        description="Optional: short notes about tone/style (e.g., noir, clipped, tense)."
    )
    last_summarized_scene: int = Field(
        description="The highest scene number included in this memory."
    )


class StoryMemorySummarizerInput(BaseModel):
    main_dramatic_concept: str
    core_plot: str
    anchor_events: Optional[List[dict]] = None
    endings: Optional[List[dict]] = None

    scenes_to_summarize: List[SceneToSummarize] = Field(
        description="Scenes included in this summarization pass."
    )

    current_story_memory: Optional[StoryMemory] = Field(
        default=None,
        description="If provided, update/overwrite it without growing forever."
    )


class StoryMemorySummarizerOutput(BaseModel):
    story_memory: StoryMemory


# ===========================================================================
# SCHEMA BLOCK: STATE CANONICALIZER (backend/state_canonicalizer.py or similar)
# ===========================================================================

# These schemas define the structured JSON output for the State Canonicalizer call:
# given canonical state + failed updates, it returns corrected updates that match
# the canonical names so the backend can safely apply changes.
#
# Note: This block assumes BaseModel, Field, List, Optional, Dict, Literal are already
# imported in backend/schemas.py.


class FailedInventoryUpdate(BaseModel):
    name: str = Field(description="Item name from Director output that failed to match canonical inventory.")
    new_count: int = Field(description="Final count requested by Director.")
    reason: Optional[str] = Field(
        default=None,
        description="Short explanation from the Director for why the item was added or why its count changed (only present when item is new or increases from 0).",
    )
    note: Optional[str] = Field(
        default=None,
        description="Non-prescriptive hint about what the item is, why it matters, or how it might help. No instructions. Only present when item is new or increases from 0.",
    )
    added_turn: Optional[int] = Field(
        default=None,
        description="Turn number when the item was first added to inventory. Only present when item is new or increases from 0.",
    )


class FailedSkillUpdate(BaseModel):
    domain: Literal["SENSE", "TALK", "MOVE", "MAKE", "ENDURE"] = Field(description="Skill domain.")
    name: str = Field(description="Skill name from Director output that failed to match canonical skills.")
    delta: Literal[-1, 0, 1] = Field(description="Delta requested by Director.")
    new_value: int = Field(description="New value requested by Director.")
    reason: Optional[str] = Field(
        default=None,
        description="One short line explaining why this skill delta was requested in the story context.",
    )


class CanonicalizerInput(BaseModel):
    canonical_inventory: List[str] = Field(
        description="Canonical inventory item names currently stored in system state."
    )
    canonical_skills_by_domain: Dict[str, List[str]] = Field(
        description="Canonical skill names by domain currently stored in system state."
    )
    failed_inventory_updates: List[FailedInventoryUpdate] = Field(
        description="Only the inventory updates that failed to apply."
    )
    failed_skill_update: Optional[FailedSkillUpdate] = Field(
        default=None,
        description="Only the skill update that failed to apply (if any)."
    )

    # Optional context only for ambiguity resolution
    scene_excerpt: Optional[str] = Field(
        default=None,
        description="Optional short excerpt of the scene text (1–3 sentences) for disambiguation."
    )
    player_action: Optional[str] = Field(
        default=None,
        description="Optional raw player action for disambiguation."
    )


class InventoryNameFix(BaseModel):
    before: str = Field(description="Non-canonical inventory name received.")
    after: str = Field(description="Canonical inventory name to use.")
    reason: str = Field(description="Why this mapping was chosen.")


class SkillNameFix(BaseModel):
    domain: Literal["SENSE", "TALK", "MOVE", "MAKE", "ENDURE"] = Field(description="Skill domain.")
    before: str = Field(description="Non-canonical skill name received.")
    after: str = Field(description="Canonical skill name to use.")
    reason: str = Field(description="Why this mapping was chosen.")


class CanonicalizerOutput(BaseModel):
    corrected_inventory_updates: List[FailedInventoryUpdate] = Field(
        description="Same updates but with canonical item names."
    )
    corrected_skill_update: Optional[FailedSkillUpdate] = Field(
        default=None,
        description="Same update but with canonical skill name (if provided)."
    )
    inventory_name_fixes: List[InventoryNameFix] = Field(
        description="Applied inventory renames."
    )
    skill_name_fixes: List[SkillNameFix] = Field(
        description="Applied skill renames."
    )
    warnings: List[str] = Field(
        description="Human-readable notes about ambiguity, low-confidence mappings, or cases where no safe canonical mapping was found. Backend should log these."
    )
