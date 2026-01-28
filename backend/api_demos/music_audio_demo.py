# backend/api_demos/music_audio_demo.py
import asyncio
import wave
from pathlib import Path

from google import genai
from google.genai import types

from pathlib import Path

import os
from dotenv import load_dotenv

# /backend/audio_demo.py -> repo root is one level up
ROOT_DIR = Path(__file__).resolve().parents[1]
load_dotenv(ROOT_DIR / ".env")

api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
if not api_key:
    raise ValueError("Missing GEMINI_API_KEY / GOOGLE_API_KEY in root .env")

client = genai.Client(api_key=api_key, http_options={"api_version": "v1alpha"})


BASE_DIR = Path(__file__).resolve().parent          # -> /backend
OUT_DIR  = BASE_DIR / "music_tests"                 # -> /backend/music_tests
OUT_DIR.mkdir(parents=True, exist_ok=True)

OUT_WAV = OUT_DIR / "noir_jazz.wav"                 # -> /backend/music_tests/noir_jazz.wav

# Lyria RealTime outputs: 48kHz, stereo, 16-bit PCM
SAMPLE_RATE = 48000
CHANNELS = 2
SAMPLE_WIDTH = 2  # bytes (16-bit)

DURATION_SECONDS = 20  # how long you want to capture


def write_wav(path: Path, pcm_bytes: bytes, channels=2, rate=48000, sample_width=2):
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(sample_width)
        wf.setframerate(rate)
        wf.writeframes(pcm_bytes)


async def main():
    # Note: docs use v1alpha for Lyria RealTime
    client = genai.Client(http_options={"api_version": "v1alpha"})

    pcm_buffer = bytearray()
    target_bytes = DURATION_SECONDS * SAMPLE_RATE * CHANNELS * SAMPLE_WIDTH

    async with client.aio.live.music.connect(model="models/lyria-realtime-exp") as session:
        # 1) Initial prompt blend
        await session.set_weighted_prompts(
            prompts=[
                types.WeightedPrompt(text="film noir jazz", weight=1.0),
                types.WeightedPrompt(text="smoky late-night saxophone", weight=1.0),
                types.WeightedPrompt(text="upright bass, brushed drums", weight=0.8),
                types.WeightedPrompt(text="tense detective atmosphere", weight=0.7),
            ]
        )

        # 2) Config (optional, but useful)
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

        # 3) Start streaming
        await session.play()

        # 4) Receive audio chunks until we have enough bytes
        while len(pcm_buffer) < target_bytes:
            async for message in session.receive():
                # Some messages may not contain audio, so guard it.
                sc = getattr(message, "server_content", None)
                if not sc or not getattr(sc, "audio_chunks", None):
                    continue

                chunk = sc.audio_chunks[0].data  # raw PCM bytes
                if chunk:
                    pcm_buffer.extend(chunk)

                if len(pcm_buffer) >= target_bytes:
                    break

        # 5) Stop
        await session.stop()

    # 6) Save WAV
    write_wav(OUT_WAV, bytes(pcm_buffer[:target_bytes]), channels=CHANNELS, rate=SAMPLE_RATE, sample_width=SAMPLE_WIDTH)
    print("Saved:", OUT_WAV.resolve())


if __name__ == "__main__":
    asyncio.run(main())
