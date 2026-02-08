from __future__ import annotations

import asyncio
import io
import os
import tempfile
import time
from pathlib import Path
from typing import Optional

from google import genai
from google.genai import types

from backend.clients import get_genai_client
from backend.ephemeral_media import delete_media_by_path

ROOT_DIR = Path(__file__).resolve().parents[1]

MEDIA_DIR = ROOT_DIR / "media"
IMAGE_DIR = MEDIA_DIR / "images"
AUDIO_DIR = MEDIA_DIR / "audio"
VIDEO_DIR = MEDIA_DIR / "video"

IMAGE_RETENTION_SECONDS = int(os.getenv("MEDIA_IMAGE_RETENTION_SECONDS", "600"))
AUDIO_RETENTION_SECONDS = int(os.getenv("MEDIA_AUDIO_RETENTION_SECONDS", "900"))
VIDEO_RETENTION_SECONDS = int(os.getenv("MEDIA_VIDEO_RETENTION_SECONDS", "900"))

PROTECTED_IMAGE_FILES = {
    "title_acff3de5_A.png",
    "title_acff3de5_B.png",
    "title_acff3de5_C.png",
}


def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _relative_path(path: Path) -> Path:
    try:
        return path.relative_to(ROOT_DIR)
    except ValueError:
        return path


def _resolve_media_path(path: str | Path) -> Optional[Path]:
    if not path:
        return None
    resolved = Path(path)
    if not resolved.is_absolute():
        resolved = ROOT_DIR / resolved
    try:
        resolved = resolved.resolve()
    except FileNotFoundError:
        resolved = resolved.absolute()
    try:
        resolved.relative_to(MEDIA_DIR)
    except ValueError:
        return None
    return resolved


def delete_media_files(paths: list[str | Path]) -> None:
    for path in paths:
        if isinstance(path, str) and delete_media_by_path(path):
            continue
        resolved = _resolve_media_path(path)
        if resolved is None:
            continue
        if resolved.name in PROTECTED_IMAGE_FILES:
            continue
        try:
            resolved.unlink(missing_ok=True)
        except FileNotFoundError:
            continue


def cleanup_expired_media(now: Optional[float] = None) -> None:
    timestamp = now or time.time()
    dir_specs = [
        (IMAGE_DIR, IMAGE_RETENTION_SECONDS, PROTECTED_IMAGE_FILES),
        (AUDIO_DIR, AUDIO_RETENTION_SECONDS, set()),
        (VIDEO_DIR, VIDEO_RETENTION_SECONDS, set()),
    ]

    for directory, ttl_seconds, protected in dir_specs:
        if ttl_seconds <= 0 or not directory.exists():
            continue
        for candidate in directory.iterdir():
            if not candidate.is_file():
                continue
            if candidate.name in protected:
                continue
            try:
                age_seconds = timestamp - candidate.stat().st_mtime
            except FileNotFoundError:
                continue
            if age_seconds > ttl_seconds:
                try:
                    candidate.unlink(missing_ok=True)
                except FileNotFoundError:
                    continue


def generate_scene_image(
    prompt: str,
    filename: str = "scene.png",
    api_key: Optional[str] = None,
    aspect_ratio: str = "16:9",
) -> Path:
    client = get_genai_client(api_key=api_key)

    chat = client.chats.create(
        model="gemini-2.5-flash-image",
        config=types.GenerateContentConfig(
            response_modalities=["TEXT", "IMAGE"],
            image_config=types.ImageConfig(
                aspect_ratio=aspect_ratio,
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
            return _relative_path(out_path)

    raise RuntimeError("No image found in response.parts")


def _write_wav(path: Path, pcm: bytes, channels: int = 1, rate: int = 24000, sample_width: int = 2) -> None:
    import wave

    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(sample_width)
        wf.setframerate(rate)
        wf.writeframes(pcm)


def _wav_bytes(pcm: bytes, channels: int = 1, rate: int = 24000, sample_width: int = 2) -> bytes:
    import wave

    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(sample_width)
        wf.setframerate(rate)
        wf.writeframes(pcm)
    return buffer.getvalue()


def _downsample_music_pcm(
    pcm: bytes,
    input_rate: int = 48000,
    input_channels: int = 2,
    output_rate: int = 24000,
    output_channels: int = 1,
    sample_width: int = 2,
) -> tuple[bytes, int, int]:
    import audioop

    converted = pcm
    channels = input_channels

    if input_channels == 2 and output_channels == 1:
        converted = audioop.tomono(converted, sample_width, 0.5, 0.5)
        channels = 1
    elif input_channels == 1 and output_channels == 2:
        converted = audioop.tostereo(converted, sample_width, 1, 1)
        channels = 2

    if input_rate != output_rate:
        converted, _ = audioop.ratecv(
            converted,
            sample_width,
            channels,
            input_rate,
            output_rate,
            None,
        )

    return converted, channels, output_rate


def generate_scene_image_bytes(
    prompt: str,
    api_key: Optional[str] = None,
    aspect_ratio: str = "16:9",
) -> bytes:
    client = get_genai_client(api_key=api_key)

    chat = client.chats.create(
        model="gemini-2.5-flash-image",
        config=types.GenerateContentConfig(
            response_modalities=["TEXT", "IMAGE"],
            image_config=types.ImageConfig(
                aspect_ratio=aspect_ratio,
            ),
        ),
    )

    response = chat.send_message(prompt)

    for part in response.parts:
        if part.text is not None:
            continue
        inline = getattr(part, "inline_data", None)
        if inline is not None and getattr(inline, "data", None):
            return inline.data
        img = part.as_image()
        if img is None:
            continue
        # Gemini SDK Image.save supports a file path (not PIL-style format kwargs).
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp_file:
            tmp_path = Path(tmp_file.name)
        try:
            img.save(str(tmp_path))
            return tmp_path.read_bytes()
        finally:
            tmp_path.unlink(missing_ok=True)

    raise RuntimeError("No image found in response.parts")


def generate_tts(text: str, filename: str = "narrator.wav", api_key: Optional[str] = None) -> Path:
    client = get_genai_client(api_key=api_key)

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
    return _relative_path(out_path)


def generate_tts_bytes(text: str, api_key: Optional[str] = None) -> bytes:
    client = get_genai_client(api_key=api_key)

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
    return _wav_bytes(audio_data)


async def _generate_music_async(
    prompt: str,
    filename: str = "music.wav",
    duration_seconds: int = 20,
    api_key: Optional[str] = None,
) -> Path:
    pcm_buffer = await _generate_music_pcm_async(
        prompt=prompt,
        duration_seconds=duration_seconds,
        api_key=api_key,
    )

    _ensure_dir(AUDIO_DIR)
    out_path = AUDIO_DIR / filename
    _write_wav(out_path, pcm_buffer, channels=2, rate=48000, sample_width=2)
    return _relative_path(out_path)


async def _generate_music_pcm_async(
    prompt: str,
    duration_seconds: int = 20,
    api_key: Optional[str] = None,
) -> bytes:
    client = get_genai_client(api_version="v1alpha", api_key=api_key)

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

        while len(pcm_buffer) < target_bytes:
            async for message in session.receive():
                sc = getattr(message, "server_content", None)
                if not sc or not getattr(sc, "audio_chunks", None):
                    continue
                chunk = sc.audio_chunks[0].data
                if chunk:
                    pcm_buffer.extend(chunk)
                if len(pcm_buffer) >= target_bytes:
                    break

        await session.stop()

    return bytes(pcm_buffer)


def generate_music(
    prompt: str,
    filename: str = "music.wav",
    duration_seconds: int = 20,
    api_key: Optional[str] = None,
) -> Path:
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        return asyncio.run_coroutine_threadsafe(
            _generate_music_async(prompt, filename, duration_seconds, api_key), loop
        ).result()

    return asyncio.run(_generate_music_async(prompt, filename, duration_seconds, api_key))


def generate_music_bytes(
    prompt: str,
    duration_seconds: int = 20,
    api_key: Optional[str] = None,
) -> bytes:
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        pcm = asyncio.run_coroutine_threadsafe(
            _generate_music_pcm_async(prompt, duration_seconds, api_key), loop
        ).result()
    else:
        pcm = asyncio.run(_generate_music_pcm_async(prompt, duration_seconds, api_key))

    # Reduce transport size for smoother browser playback on production links.
    optimized_pcm, optimized_channels, optimized_rate = _downsample_music_pcm(
        pcm,
        input_rate=48000,
        input_channels=2,
        output_rate=24000,
        output_channels=1,
        sample_width=2,
    )
    return _wav_bytes(
        optimized_pcm,
        channels=optimized_channels,
        rate=optimized_rate,
        sample_width=2,
    )


def _generate_first_frame(prompt: str, api_key: Optional[str] = None) -> types.Image:
    client = get_genai_client(api_key=api_key)
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
    op_error = getattr(operation, "error", None)
    if op_error:
        raise RuntimeError(f"Video generation operation failed: {op_error}")
    return operation


def generate_ending_video(
    prompt: str,
    filename: str = "ending.mp4",
    first_frame_path: Optional[Path] = None,
    api_key: Optional[str] = None,
) -> Path:
    # Veo preview features can vary by API version; prefer v1alpha with fallback.
    client = get_genai_client(api_version="v1alpha", api_key=api_key)

    if first_frame_path is not None:
        resolved_first = first_frame_path
        if not resolved_first.is_absolute():
            resolved_first = ROOT_DIR / resolved_first
        if resolved_first.exists():
            first_frame = types.Image.from_file(location=str(resolved_first))
        else:
            first_frame = _generate_first_frame(prompt, api_key=api_key)
    else:
        first_frame = _generate_first_frame(prompt, api_key=api_key)

    operation_kwargs = {
        "model": "veo-3.1-fast-generate-preview",
        "prompt": prompt,
        "image": first_frame,
    }

    def _start_generation(active_client: genai.Client):
        return active_client.models.generate_videos(**operation_kwargs)

    try:
        operation = _start_generation(client)
        operation = _poll_until_done(client, operation)
    except Exception:
        # Retry once on default API version in case account/project is configured there.
        client = get_genai_client(api_key=api_key)
        operation = _start_generation(client)
        operation = _poll_until_done(client, operation)

    _ensure_dir(VIDEO_DIR)
    out_path = VIDEO_DIR / filename

    response = getattr(operation, "response", None)
    generated = getattr(response, "generated_videos", None) if response else None
    if not generated:
        raise RuntimeError("Video generation returned no generated_videos in operation response.")
    video_obj = generated[0]
    client.files.download(file=video_obj.video)
    video_obj.video.save(str(out_path))

    return _relative_path(out_path)
