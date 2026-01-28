# backend/api_demos/title_screen_selector_demo.py

import json
from google import genai
from backend.schemas import TitleScreenSelectorOutput


PROMPT = """
You are the Title Screen Selector for an AI-driven interactive fiction game.

GOAL
Generate exactly 3 distinct, highly hooky game story concepts that feel exciting immediately.

RULES
- Provide exactly 3 ideas.
- Each title must be 2–6 words.
- Each one_liner must be ONE single line (no line breaks), and must imply a problem or danger.
- The three ideas must be diverse in setting/genre (avoid overlap).
- Do not include lists, bullets, or commentary.

COVER IMAGE PROMPT RULES
- For each idea, provide a cover_image_prompt that looks like a premium game cover.
- The prompt must specify: style, mood, lighting, composition, and key elements.
- No text in the image. No logos. No watermarks. No readable typography.
""".strip()


def main() -> None:
    client = genai.Client()

    response = client.models.generate_content(
        model="gemini-3-flash-preview",
        contents=PROMPT,
        config={
            "response_mime_type": "application/json",
            "response_json_schema": TitleScreenSelectorOutput.model_json_schema(),
        },
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
