from __future__ import annotations

from typing import Any, Optional


def _zero_usage() -> dict[str, int]:
    return {
        "input_tokens": 0,
        "thinking_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
    }


def extract_usage_metadata(response: Any) -> dict[str, int]:
    usage = getattr(response, "usage_metadata", None)
    if usage is None:
        return _zero_usage()

    def _to_int(value: Any) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0

    return {
        "input_tokens": _to_int(getattr(usage, "prompt_token_count", 0)),
        "thinking_tokens": _to_int(getattr(usage, "thoughts_token_count", 0)),
        "output_tokens": _to_int(getattr(usage, "candidates_token_count", 0)),
        "total_tokens": _to_int(getattr(usage, "total_token_count", 0)),
    }


def ensure_token_usage_state(state: dict[str, Any]) -> dict[str, Any]:
    token_usage = state.setdefault("token_usage", {})
    token_usage.setdefault("totals", _zero_usage())
    token_usage.setdefault("by_call_type", {})
    token_usage.setdefault("events", [])
    return token_usage


def record_token_usage(
    state: dict[str, Any],
    call_type: str,
    usage: dict[str, int],
    *,
    turn_number: Optional[int] = None,
) -> dict[str, Any]:
    token_usage = ensure_token_usage_state(state)
    totals = token_usage["totals"]

    for key in ("input_tokens", "thinking_tokens", "output_tokens", "total_tokens"):
        totals[key] = int(totals.get(key, 0)) + int(usage.get(key, 0))

    by_call_type = token_usage["by_call_type"]
    bucket = by_call_type.setdefault(call_type, _zero_usage())
    for key in ("input_tokens", "thinking_tokens", "output_tokens", "total_tokens"):
        bucket[key] = int(bucket.get(key, 0)) + int(usage.get(key, 0))

    token_usage["events"].append(
        {
            "call_type": call_type,
            "turn_number": turn_number,
            **usage,
        }
    )
    return token_usage

