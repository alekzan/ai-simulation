from __future__ import annotations

import json
from typing import Any, Type

from pydantic import BaseModel, ValidationError


class StructuredOutputValidationError(Exception):
    def __init__(self, message: str, details: Any | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details

    def to_error_payload(self) -> dict:
        return {
            "error_type": "SCHEMA_VALIDATION_ERROR",
            "message": self.message,
            "details": self.details,
        }


def validate_model_json(raw_text: str, model_cls: Type[BaseModel]) -> BaseModel:
    try:
        if hasattr(model_cls, "model_validate_json"):
            return model_cls.model_validate_json(raw_text)  # pydantic v2
        return model_cls.parse_raw(raw_text)  # pydantic v1 fallback
    except ValidationError as exc:
        raise StructuredOutputValidationError(
            "Model output failed schema validation.",
            details=exc.errors(),
        ) from exc
    except json.JSONDecodeError as exc:
        raise StructuredOutputValidationError(
            "Model output is not valid JSON.",
            details={"error": str(exc)},
        ) from exc


def validate_inventory_image_rules(
    inventory_changes: list[Any],
    prior_inventory_counts: dict[str, int],
) -> None:
    violations: list[dict[str, Any]] = []

    for change in inventory_changes:
        name = getattr(change, "name", None)
        new_count = getattr(change, "new_count", None)
        image_prompt = getattr(change, "image_prompt", None)

        prev_count = prior_inventory_counts.get(name, 0) if name is not None else 0
        is_new_item = prev_count == 0 and isinstance(new_count, int) and new_count > 0

        has_image_prompt = isinstance(image_prompt, str) and image_prompt.strip() != ""

        if is_new_item and not has_image_prompt:
            violations.append(
                {
                    "name": name,
                    "reason": "image_prompt required for new item",
                    "previous_count": prev_count,
                    "new_count": new_count,
                }
            )
        if not is_new_item and image_prompt is not None:
            violations.append(
                {
                    "name": name,
                    "reason": "image_prompt must be absent for non-new item",
                    "previous_count": prev_count,
                    "new_count": new_count,
                }
            )

    if violations:
        raise StructuredOutputValidationError(
            "Inventory image_prompt rules violated.",
            details={"violations": violations},
        )
