# backend/api_demos/video_generation_demo.py

from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT_DIR))
"""
DEMO FILE: IMAGE TO VIDEO (Veo) - TWO MODES

Purpose
- Show Codex how to generate a video using Veo with an image as the first frame.
- Mode A: Generate the first frame with Gemini image model, then pass it to Veo.
- Mode B: Load a local PNG as the first frame, then pass it to Veo.

Notes
- Demo-only code, not production.
- Assumes your API key is already available to the Google GenAI SDK via env vars or client config.
"""

import time
from pathlib import Path

from google import genai
from google.genai import types


def poll_until_done(client: genai.Client, operation, sleep_seconds: int = 10):
    while not operation.done:
        print("Waiting for video generation to complete...")
        time.sleep(sleep_seconds)
        operation = client.operations.get(operation)
    return operation


def save_video_from_operation(client: genai.Client, operation, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)

    video_obj = operation.response.generated_videos[0]
    client.files.download(file=video_obj.video)
    video_obj.video.save(str(out_path))

    print("Saved:", out_path.resolve())


def generate_first_frame_with_gemini(client: genai.Client, prompt: str) -> types.Image:
    image_resp = client.models.generate_content(
        model="gemini-2.5-flash-image",
        contents=prompt,
        config={"response_modalities": ["IMAGE"]},
    )

    first_frame = image_resp.parts[0].as_image()
    if first_frame is None:
        raise RuntimeError("No image returned from gemini-2.5-flash-image")
    return first_frame


def load_first_frame_from_file(img_path: Path) -> types.Image:
    # This is the cleanest way: the SDK builds bytesBase64Encoded + mimeType internally.
    return types.Image.from_file(str(img_path))


def generate_video_from_first_frame(
    client: genai.Client,
    prompt: str,
    first_frame: types.Image,
    model: str = "veo-3.1-fast-generate-preview",
):
    operation = client.models.generate_videos(
        model=model,
        prompt=prompt,
        image=first_frame,
    )
    return operation


def main() -> None:
    client = genai.Client()

    out_dir = Path("video_tests")
    out_dir.mkdir(parents=True, exist_ok=True)

    # -------------------------
    # MODE A: Generate image -> use as first frame -> Veo video
    # -------------------------
    prompt_a = (
        "Panning wide shot of a smoky film noir jazz bar at night. "
        "A lone detective in a trench coat sits under a dim spotlight. "
        "High-contrast black and white, neon reflections, drifting cigarette smoke."
    )

    first_frame_a = generate_first_frame_with_gemini(client, prompt_a)

    op_a = generate_video_from_first_frame(
        client=client,
        prompt=prompt_a,
        first_frame=first_frame_a,
        model="veo-3.1-fast-generate-preview",
    )
    op_a = poll_until_done(client, op_a)

    save_video_from_operation(client, op_a, out_dir / "veo_from_generated_image.mp4")

    # -------------------------
    # MODE B: Local image file -> use as first frame -> Veo video
    # -------------------------
    prompt_b = (
        "Slow dolly-in through rain and neon toward the jazz bar entrance. "
        "Keep the same noir mood, black and white, dramatic shadows, subtle film grain."
    )

    img_path = Path("image_tests") / "scene_1_v3.png"
    first_frame_b = load_first_frame_from_file(img_path)

    op_b = generate_video_from_first_frame(
        client=client,
        prompt=prompt_b,
        first_frame=first_frame_b,
        model="veo-3.1-fast-generate-preview",
    )
    op_b = poll_until_done(client, op_b)

    save_video_from_operation(client, op_b, out_dir / "veo_from_scene_1_v3.mp4")


if __name__ == "__main__":
    main()
