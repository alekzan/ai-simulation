from __future__ import annotations

import os
import secrets
import threading
import time
from dataclasses import dataclass
from typing import Optional

EPHEMERAL_IMAGE_TTL_SECONDS = int(os.getenv("EPHEMERAL_IMAGE_TTL_SECONDS", "600"))
EPHEMERAL_TTS_TTL_SECONDS = int(os.getenv("EPHEMERAL_TTS_TTL_SECONDS", "600"))
EPHEMERAL_MUSIC_TTL_SECONDS = int(os.getenv("EPHEMERAL_MUSIC_TTL_SECONDS", "1800"))
EPHEMERAL_VIDEO_TTL_SECONDS = int(os.getenv("EPHEMERAL_VIDEO_TTL_SECONDS", "900"))

EPHEMERAL_PATH_PREFIX = "/ephemeral/"


@dataclass
class EphemeralMedia:
    data: bytes
    mime_type: str
    last_access: float
    ttl_seconds: int


_LOCK = threading.Lock()
_MEDIA_STORE: dict[str, EphemeralMedia] = {}


def _now() -> float:
    return time.time()


def build_ephemeral_path(token: str) -> str:
    return f"{EPHEMERAL_PATH_PREFIX}{token}"


def token_from_path(path: str) -> Optional[str]:
    if not path:
        return None
    if path.startswith(EPHEMERAL_PATH_PREFIX):
        return path[len(EPHEMERAL_PATH_PREFIX) :]
    if path.startswith("ephemeral://"):
        return path[len("ephemeral://") :]
    return None


def store_media(data: bytes, mime_type: str, ttl_seconds: int) -> str:
    token = secrets.token_urlsafe(18)
    timestamp = _now()
    with _LOCK:
        _MEDIA_STORE[token] = EphemeralMedia(
            data=data,
            mime_type=mime_type,
            last_access=timestamp,
            ttl_seconds=ttl_seconds,
        )
    return token


def get_media(token: str) -> Optional[tuple[bytes, str]]:
    timestamp = _now()
    with _LOCK:
        item = _MEDIA_STORE.get(token)
        if item is None:
            return None
        if item.ttl_seconds > 0 and timestamp - item.last_access > item.ttl_seconds:
            _MEDIA_STORE.pop(token, None)
            return None
        item.last_access = timestamp
        return item.data, item.mime_type


def delete_media(token: str) -> None:
    with _LOCK:
        _MEDIA_STORE.pop(token, None)


def delete_media_by_path(path: str) -> bool:
    token = token_from_path(path)
    if not token:
        return False
    delete_media(token)
    return True


def prune_expired_media(now: Optional[float] = None) -> None:
    timestamp = now or _now()
    expired = []
    with _LOCK:
        for token, item in _MEDIA_STORE.items():
            if item.ttl_seconds <= 0:
                continue
            if timestamp - item.last_access > item.ttl_seconds:
                expired.append(token)
        for token in expired:
            _MEDIA_STORE.pop(token, None)
