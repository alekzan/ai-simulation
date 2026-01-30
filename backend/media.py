from __future__ import annotations

import asyncio
import time
from pathlib import Path
from typing import Optional

from google import genai
from google.genai import types

from backend.clients import get_genai_client

ROOT_DIR = Path(__file__).resolve().parents[1]

IMAGE_DIR = ROOT_DIR / "image_tests"
AUDIO_DIR = ROOT_DIR / "audio_tests"
VIDEO_DIR = ROOT_DIR / "video_tests"


def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def generate_scene_image(prompt: str, filename: str = "scene.png") -> Path:
    client = get_genai_client()

    chat = client.chats.create(
        model="gemini-2.5-flash-image",
        config=types.GenerateContentConfig(
            response_modalities=["TEXT", "IMAGE"],
            image_config=types.ImageConfig(
                aspect_ratio="16:9",
            ),
        ),
    )

    response = chat.send_message(prompt)

    _ensure_dir(IMAGE_DIR)
    out_path = IMAGE_DIR / filename

    for part in response.parts:
        if part.text is not None:
            continue
        img = part.as_image()
        if img is not None:
            img.save(str(out_path))
            return out_path

    raise RuntimeError("No image found in response.parts")


def _write_wav(path: Path, pcm: bytes, channels: int = 1, rate: int = 24000, sample_width: int = 2) -> None:
    import wave

    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(sample_width)
        wf.setframerate(rate)
        wf.writeframes(pcm)


def generate_tts(text: str, filename: str = "narrator.wav") -> Path:
    client = get_genai_client()

    tts_text = text if text.strip().lower().startswith("say:") else f"Say: {text}"

    response = client.models.generate_content(
        model="gemini-2.5-flash-preview-tts",
        contents=tts_text,
        config=types.GenerateContentConfig(
            response_modalities=["AUDIO"],
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(
                        voice_name="Charon",
                    )
                )
            ),
        ),
    )

    audio_data = response.candidates[0].content.parts[0].inline_data.data

    _ensure_dir(AUDIO_DIR)
    out_path = AUDIO_DIR / filename
    _write_wav(out_path, audio_data)
    return out_path


async def _generate_music_async(prompt: str, filename: str = "music.wav", duration_seconds: int = 20) -> Path:
    client = get_genai_client(api_version="v1alpha")

    sample_rate = 48000
    channels = 2
    sample_width = 2
    target_bytes = duration_seconds * sample_rate * channels * sample_width
    pcm_buffer = bytearray()

    async with client.aio.live.music.connect(model="models/lyria-realtime-exp") as session:
        await session.set_weighted_prompts(
            prompts=[types.WeightedPrompt(text=prompt, weight=1.0)]
        )

        await session.set_music_generation_config(
            config=types.LiveMusicGenerationConfig(
                bpm=78,
                temperature=1.1,
                guidance=4.0,
                density=0.55,
                brightness=0.35,
                music_generation_mode=types.MusicGenerationMode.QUALITY,
            )
        )

        await session.play()

        async for chunk in session.receive():
            if chunk is None or chunk.data is None:
                continue
            pcm_buffer.extend(chunk.data)
            if len(pcm_buffer) >= target_bytes:
                break

        await session.stop()

    _ensure_dir(AUDIO_DIR)
    out_path = AUDIO_DIR / filename
    _write_wav(out_path, bytes(pcm_buffer), channels=channels, rate=sample_rate, sample_width=sample_width)
    return out_path


def generate_music(prompt: str, filename: str = "music.wav", duration_seconds: int = 20) -> Path:
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        return asyncio.run_coroutine_threadsafe(
            _generate_music_async(prompt, filename, duration_seconds), loop
        ).result()

    return asyncio.run(_generate_music_async(prompt, filename, duration_seconds))


def _generate_first_frame(prompt: str) -> types.Image:
    client = get_genai_client()
    image_resp = client.models.generate_content(
        model="gemini-2.5-flash-image",
        contents=prompt,
        config={"response_modalities": ["IMAGE"]},
    )

    first_frame = image_resp.parts[0].as_image()
    if first_frame is None:
        raise RuntimeError("No image returned from gemini-2.5-flash-image")
    return first_frame


def _poll_until_done(client: genai.Client, operation, sleep_seconds: int = 10):
    while not operation.done:
        time.sleep(sleep_seconds)
        operation = client.operations.get(operation)
    return operation


def generate_ending_video(
    prompt: str,
    filename: str = "ending.mp4",
    first_frame_path: Optional[Path] = None,
) -> Path:
    client = get_genai_client()

    if first_frame_path is not None:
        first_frame = types.Image.from_file(str(first_frame_path))
    else:
        first_frame = _generate_first_frame(prompt)

    operation = client.models.generate_videos(
        model="veo-3.1-fast-generate-preview",
        prompt=prompt,
        image=first_frame,
    )

    operation = _poll_until_done(client, operation)

    _ensure_dir(VIDEO_DIR)
    out_path = VIDEO_DIR / filename

    video_obj = operation.response.generated_videos[0]
    client.files.download(file=video_obj.video)
    video_obj.video.save(str(out_path))

    return out_path
