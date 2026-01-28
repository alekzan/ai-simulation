from __future__ import annotations

import json
import os
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4


def get_db_path() -> Path:
    override = os.getenv("SIM_DB_PATH")
    if override:
        return Path(override)
    return Path(__file__).resolve().parent / "data" / "app.db"


@dataclass
class SessionRecord:
    session_id: str
    state_json: dict[str, Any]


def _connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: Optional[Path] = None) -> None:
    path = db_path or get_db_path()
    with _connect(path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                state_json TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            CREATE TRIGGER IF NOT EXISTS sessions_updated_at
            AFTER UPDATE ON sessions
            FOR EACH ROW
            BEGIN
                UPDATE sessions SET updated_at = CURRENT_TIMESTAMP WHERE session_id = OLD.session_id;
            END;
            """
        )


def create_session(initial_state_json: dict[str, Any], db_path: Optional[Path] = None) -> str:
    path = db_path or get_db_path()
    session_id = str(uuid4())
    payload = json.dumps(initial_state_json, ensure_ascii=False)
    with _connect(path) as conn:
        conn.execute(
            "INSERT INTO sessions (session_id, state_json) VALUES (?, ?)",
            (session_id, payload),
        )
    return session_id


def get_session(session_id: str, db_path: Optional[Path] = None) -> Optional[SessionRecord]:
    path = db_path or get_db_path()
    with _connect(path) as conn:
        row = conn.execute(
            "SELECT session_id, state_json FROM sessions WHERE session_id = ?",
            (session_id,),
        ).fetchone()
    if not row:
        return None
    return SessionRecord(session_id=row["session_id"], state_json=json.loads(row["state_json"]))


def save_session(session_id: str, state_json: dict[str, Any], db_path: Optional[Path] = None) -> None:
    path = db_path or get_db_path()
    payload = json.dumps(state_json, ensure_ascii=False)
    with _connect(path) as conn:
        conn.execute(
            "UPDATE sessions SET state_json = ? WHERE session_id = ?",
            (payload, session_id),
        )
