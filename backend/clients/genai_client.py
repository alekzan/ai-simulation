from __future__ import annotations

import os
from typing import Optional

from google import genai
from google.genai import types
from dotenv import load_dotenv
from pathlib import Path


DEFAULT_THINKING_LEVEL = "minimal"


def get_genai_client(api_version: Optional[str] = None) -> genai.Client:
    root_dir = Path(__file__).resolve().parents[2]
    load_dotenv(root_dir / ".env")
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    kwargs = {}
    if api_key:
        kwargs["api_key"] = api_key
    if api_version:
        kwargs["http_options"] = {"api_version": api_version}
    return genai.Client(**kwargs)


def get_thinking_config() -> types.ThinkingConfig:
    level = os.getenv("GEMINI_THINKING_LEVEL", DEFAULT_THINKING_LEVEL)
    return types.ThinkingConfig(thinking_level=level)
