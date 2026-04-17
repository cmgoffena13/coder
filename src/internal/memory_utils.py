from datetime import datetime
from pathlib import Path

from src.utils import get_coder_config_dir, read_json, write_json


def get_chat_sessions_dir() -> Path:
    """Return the directory for saved Textual chat sessions."""
    return get_coder_config_dir("chat_sessions")


def get_chat_sessions_index_path() -> Path:
    """Return the chat sessions index JSON path."""
    return get_chat_sessions_dir() / "sessions_index.json"


def new_chat_session_filename() -> str:
    """Create a timestamped JSON filename for a chat session."""
    return f"{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.json"


def new_chat_session_path() -> Path:
    """Return a new timestamped chat session path."""
    return get_chat_sessions_dir() / new_chat_session_filename()


def resolve_chat_session_path(filename: str) -> Path:
    """Resolve a session filename to an absolute path in the sessions dir."""
    return get_chat_sessions_dir() / filename


def _read_sessions_index() -> list[dict[str, str]]:
    """Read the chat sessions index from the file."""
    index_path = get_chat_sessions_index_path()
    if not index_path.exists():
        _write_sessions_index([])
        return []

    data = read_json(index_path)

    entries: list[dict[str, str]] = []
    for item in data:
        filename = str(item["filename"]).strip()
        first_prompt = str(item["first_prompt"]).strip()
        entries.append({"filename": filename, "first_prompt": first_prompt})
    return entries


def _write_sessions_index(entries: list[dict[str, str]]) -> None:
    """Write the chat sessions index to the file."""
    index_path = get_chat_sessions_index_path()
    write_json(index_path, entries)


def list_chat_sessions_index() -> list[dict[str, str]]:
    """Sessions from ``sessions_index.json`` only (newest filename first)."""
    index_name = get_chat_sessions_index_path().name
    entries = [e for e in _read_sessions_index() if e.get("filename") != index_name]
    entries.sort(key=lambda item: item["filename"], reverse=True)
    return entries


def upsert_chat_session_index(filename: str, first_prompt: str) -> None:
    """Insert or replace one session index row (caller passes the first user prompt)."""
    entries = _read_sessions_index()
    by_filename = {entry["filename"]: entry for entry in entries}
    by_filename[filename] = {"filename": filename, "first_prompt": first_prompt}
    merged = sorted(
        by_filename.values(), key=lambda item: item["filename"], reverse=True
    )
    _write_sessions_index(merged)


def delete_chat_session(filename: str) -> None:
    """Delete a saved chat session file and remove it from index."""
    path = resolve_chat_session_path(filename)
    try:
        path.unlink(missing_ok=True)
    except Exception:
        raise ValueError(f"Failed to delete session file: {path}")

    entries = _read_sessions_index()
    filtered = [entry for entry in entries if entry["filename"] != filename]
    filtered.sort(key=lambda item: item["filename"], reverse=True)
    _write_sessions_index(filtered)
