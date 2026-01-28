import tempfile
from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from backend.db import create_session, get_session, init_db, save_session


def test_db_roundtrip() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "app.db"
        init_db(db_path)

        initial_state = {"turn_number": 1, "skills": [], "inventory": []}
        session_id = create_session(initial_state, db_path)

        record = get_session(session_id, db_path)
        assert record is not None
        assert record.state_json["turn_number"] == 1

        updated_state = {**record.state_json, "turn_number": 2}
        save_session(session_id, updated_state, db_path)

        record2 = get_session(session_id, db_path)
        assert record2 is not None
        assert record2.state_json["turn_number"] == 2


if __name__ == "__main__":
    test_db_roundtrip()
    print("db_smoke: ok")
