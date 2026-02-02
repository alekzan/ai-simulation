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

