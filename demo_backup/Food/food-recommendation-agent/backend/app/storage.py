from __future__ import annotations

import json
import os
import threading
import uuid
from pathlib import Path
from typing import Any

from dotenv import load_dotenv


_LOCK = threading.RLock()
_STORE: dict[str, dict[str, Any]] = {}
_STORE_PATH: Path | None = None


def _normalize_session(session: dict[str, Any]) -> dict[str, Any]:
    session.setdefault("old_intent", None)
    session.setdefault("messages", [])
    session.setdefault("last_recommendations", [])
    session.setdefault("last_filters", {})
    return session


def _backend_dir() -> Path:
    return Path(__file__).resolve().parents[1]


def _project_dir() -> Path:
    return _backend_dir().parent


def resolve_store_path(raw_path: str | None = None) -> Path:
    load_dotenv()
    configured_path = raw_path or os.getenv("CHAT_STORE_PATH", "backend/chat_store.json")
    path = Path(configured_path)
    if path.is_absolute():
        return path

    candidates = [
        Path.cwd() / path,
        _project_dir() / path,
        _backend_dir() / path,
    ]

    path_parts = path.parts
    if path_parts and path_parts[0] == "backend":
        stripped = Path(*path_parts[1:])
        candidates.extend(
            [
                _backend_dir() / stripped,
                Path.cwd() / stripped,
            ]
        )

    for candidate in candidates:
        if candidate.exists():
            return candidate

    return candidates[0]


def load_store() -> dict[str, dict[str, Any]]:
    global _STORE, _STORE_PATH
    with _LOCK:
        _STORE_PATH = resolve_store_path()
        if not _STORE_PATH.exists():
            _STORE = {}
            return _STORE

        try:
            with _STORE_PATH.open("r", encoding="utf-8") as file:
                payload = json.load(file)
        except (json.JSONDecodeError, OSError):
            payload = {}

        _STORE = payload if isinstance(payload, dict) else {}
        for session_id, session in list(_STORE.items()):
            if isinstance(session, dict):
                session.setdefault("session_id", session_id)
                _STORE[session_id] = _normalize_session(session)
        return _STORE


def save_store() -> None:
    with _LOCK:
        path = _STORE_PATH or resolve_store_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as file:
            json.dump(_STORE, file, ensure_ascii=False, indent=2)


def create_session(session_id: str | None = None) -> dict[str, Any]:
    with _LOCK:
        new_session_id = session_id or str(uuid.uuid4())
        _STORE[new_session_id] = {
            "session_id": new_session_id,
            "old_intent": None,
            "messages": [],
            "last_recommendations": [],
            "last_filters": {},
        }
        save_store()
        return _STORE[new_session_id]


def get_session(session_id: str) -> dict[str, Any] | None:
    with _LOCK:
        session = _STORE.get(session_id)
        return _normalize_session(session) if session else None


def ensure_session(session_id: str | None = None) -> dict[str, Any]:
    with _LOCK:
        if session_id and session_id in _STORE:
            return _normalize_session(_STORE[session_id])
        return create_session(session_id)


def save_message(session_id: str, role: str, content: str) -> None:
    with _LOCK:
        session = _STORE.get(session_id) or create_session(session_id)
        session.setdefault("messages", []).append({"role": role, "content": content})
        save_store()


def set_old_intent(session_id: str, intent: str | None) -> None:
    with _LOCK:
        session = _STORE.get(session_id) or create_session(session_id)
        session["old_intent"] = intent
        save_store()


def set_last_recommendations(session_id: str, recommendations: list[dict[str, Any]]) -> None:
    with _LOCK:
        session = _STORE.get(session_id) or create_session(session_id)
        session["last_recommendations"] = recommendations
        save_store()


def set_last_filters(session_id: str, filters: dict[str, Any]) -> None:
    with _LOCK:
        session = _STORE.get(session_id) or create_session(session_id)
        session["last_filters"] = filters
        save_store()
