# backend/api_demos/image_generation_demo.py

from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT_DIR))
"""
DEMO FILE: IMAGE GENERATION + IMAGE EDIT (SAME CHAT SESSION)

Purpose
- Show Codex how to call Gemini image generation via a chat session
- Save the returned images to disk
- Demonstrate an edit call that continues the same session (so it edits the prior image context)

Notes
- This is demo-only code, not production.
- Assumes your API key is already available to the Google GenAI SDK via env vars or client config.
"""

from pathlib import Path

from google import genai
from google.genai import types


def print_usage(resp) -> None:
    usage = getattr(resp, "usage_metadata", None)
    if not usage:
        return
    print(f"Input Tokens:    {getattr(usage, 'prompt_token_count', 'n/a')}")
    print(f"Thinking Tokens: {getattr(usage, 'thoughts_token_count', 'n/a')}")
    print(f"Output Tokens:   {getattr(usage, 'candidates_token_count', 'n/a')}")
    print(f"--------------------------")
    print(f"Total Tokens:    {getattr(usage, 'total_token_count', 'n/a')}")


def save_first_image(resp, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)

    for part in resp.parts:
        if part.text is not None:
            print(part.text)
        else:
            img = part.as_image()
            if img is not None:
                img.save(str(out_path))
                print(f"Image stored in: {out_path}")
                return

    raise RuntimeError("No image found in response.parts")


def main() -> None:
    client = genai.Client()

    chat = client.chats.create(
        model="gemini-2.5-flash-image",
        config=types.GenerateContentConfig(
            response_modalities=["TEXT", "IMAGE"],
            image_config=types.ImageConfig(
                aspect_ratio="16:9",
            ),
        ),
    )

    # 1) Generate initial image
    message = (
        "Create a moody film noir illustration set in a smoky jazz bar at night. "
        "A lone man in a trench coat and fedora sits at the bar under a dim spotlight, "
        "cigarette smoke curling through the air. The scene is high-contrast black and white "
        "with dramatic shadows, neon reflections, and a sense of mystery, like a classic 1940s detective film."
    )

    response1 = chat.send_message(message)
    print_usage(response1)
    save_first_image(response1, Path("image_tests") / "scene_1_v1.png")

    # 2) Edit the image in the same chat session (deeper change)
    edit_message = """
Transform the scene into a rain-soaked street noir exterior just outside the jazz bar.
Keep the same lone man (trench coat + fedora) as the main subject.
"""

    response2 = chat.send_message(
        edit_message,
        config=types.GenerateContentConfig(
            response_modalities=["TEXT", "IMAGE"],
            image_config=types.ImageConfig(
                aspect_ratio="16:9",
            ),
        ),
    )

    print_usage(response2)
    save_first_image(response2, Path("image_tests") / "scene_2_v1.png")


if __name__ == "__main__":
    main()
