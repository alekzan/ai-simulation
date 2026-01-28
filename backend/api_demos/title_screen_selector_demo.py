# backend/api_demos/title_screen_selector_demo.py

from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT_DIR))
import json

from google.genai import types

from backend.clients import get_genai_client, get_thinking_config
from backend.prompts.title_screen_selector import PROMPT
from backend.schemas import TitleScreenSelectorOutput


def main() -> None:
    client = get_genai_client()

    response = client.models.generate_content(
        model="gemini-3-flash-preview",
        contents=PROMPT,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_json_schema=TitleScreenSelectorOutput.model_json_schema(),
            thinking_config=get_thinking_config(),  # "high" for production
        ),
    )

    # Print tokens (guard in case usage_metadata is missing)
    usage = getattr(response, "usage_metadata", None)
    if usage:
        print(f"Input Tokens:    {getattr(usage, 'prompt_token_count', 'n/a')}")
        print(f"Thinking Tokens: {getattr(usage, 'thoughts_token_count', 'n/a')}")
        print(f"Output Tokens:   {getattr(usage, 'candidates_token_count', 'n/a')}")
        print(f"--------------------------")
        print(f"Total Tokens:    {getattr(usage, 'total_token_count', 'n/a')}")

    # Parse + print JSON
    titles = TitleScreenSelectorOutput.model_validate_json(response.text)
    print(json.dumps(titles.model_dump(), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
