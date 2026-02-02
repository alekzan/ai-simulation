import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from backend.schemas import TitleScreenSelectorOutput, InitialScriptOutput, InventoryChange
from backend.validation import (
    StructuredOutputValidationError,
    validate_model_json,
)


def test_title_selector_valid() -> None:
    payload = """
    {
      "ideas": [
        {"id": "A", "title": "Echoes in Glass", "one_liner": "A whispering vault dares you to steal the truth.", "cover_image_prompt": "Cinematic heist cover, teal lighting, glass vault, lone figure, dramatic shadows."},
        {"id": "B", "title": "Ash Tide", "one_liner": "An island burns and the tide rises with secrets.", "cover_image_prompt": "Volcanic island at dusk, stormy seas, lone survivor, high contrast, painterly."},
        {"id": "C", "title": "Silent Circuit", "one_liner": "A city goes dark and your heartbeat is the only signal.", "cover_image_prompt": "Neon city blackout, rain, lone runner, cyberpunk mood, wide angle, gritty."}
      ]
    }
    """
    parsed = validate_model_json(payload, TitleScreenSelectorOutput)
    assert len(parsed.ideas) == 3


def test_initial_script_invalid() -> None:
    bad_payload = """{"main_dramatic_concept": "Test"}"""
    try:
        validate_model_json(bad_payload, InitialScriptOutput)
    except StructuredOutputValidationError as exc:
        assert exc.to_error_payload()["error_type"] == "SCHEMA_VALIDATION_ERROR"
        return
    raise AssertionError("Expected StructuredOutputValidationError")


def test_inventory_change_schema_text_only() -> None:
    valid = InventoryChange(
        name="Keycard",
        new_count=1,
        reason="Found under the counter.",
        note="Access to restricted doors.",
        added_turn=2,
    )
    assert valid.name == "Keycard"
    assert valid.new_count == 1


if __name__ == "__main__":
    test_title_selector_valid()
    test_initial_script_invalid()
    test_inventory_change_schema_text_only()
    print("validation_smoke: ok")
