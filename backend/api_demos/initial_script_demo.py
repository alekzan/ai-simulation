# backend/api_demos/initial_script_demo.py

from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT_DIR))
import json

from google.genai import types

from backend.clients import get_genai_client, get_thinking_config
from backend.prompts.initial_script import SYSTEM_INSTRUCTION
from backend.schemas import InitialScriptOutput

# =========================================
# HARD CODED INPUT TO TEST FIRST DIRECTOR CALL
# =========================================

USER_SELECTION = "Bar of jazz at midnight: the music stops when someone recognizes you, and you realize you don't remember how you got there."
GAME_LENGTH_MODE = "SHORT"  # "SHORT" | "LONG" | "INFINITE"

TARGET_TURNS_BY_MODE = {
    "SHORT": 10,
    "LONG": 20,
    "INFINITE": None,
}
TARGET_TURNS_HINT = TARGET_TURNS_BY_MODE[GAME_LENGTH_MODE]

# =========================================
# =========================================

# ---------
# Run Gemini with structured output
# ---------

client = get_genai_client()

response = client.models.generate_content(
    model="gemini-3-flash-preview",
    config=types.GenerateContentConfig(
        system_instruction=SYSTEM_INSTRUCTION,
        response_mime_type="application/json",
        response_json_schema=InitialScriptOutput.model_json_schema(),
        thinking_config=get_thinking_config(),  # "high" for production
    ),
    contents=(
        f"Initial scenario (chosen by the player): {USER_SELECTION}\n"
        f"Game length mode: {GAME_LENGTH_MODE}\n"
        f"Target turns (hint, not mandatory): {TARGET_TURNS_HINT}"
    ),

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
initial_script = InitialScriptOutput.model_validate_json(response.text)
print(json.dumps(initial_script.model_dump(), indent=2, ensure_ascii=False))
