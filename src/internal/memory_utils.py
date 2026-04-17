import re
from datetime import datetime
from pathlib import Path
from typing import Optional

from thoughtflow import MEMORY

from src.utils import get_coder_config_dir, read_json, write_json


def get_chat_sessions_dir() -> Path:
    """Return the directory for saved Textual chat sessions."""
    return get_coder_config_dir("chat_sessions")


def get_chat_sessions_index_path() -> Path:
    """Return the chat sessions index JSON path."""
    return get_chat_sessions_dir() / "sessions_index.json"


_SESSION_PREFIX_UNSAFE_RE = re.compile(r"[^A-Za-z0-9._-]+")


def _sanitize_session_prefix(text: str) -> str:
    cleaned = _SESSION_PREFIX_UNSAFE_RE.sub("-", str(text))
    cleaned = cleaned.strip("-._")
    return cleaned or "cwd"


def new_chat_session_filename(cwd: Path) -> str:
    """Create a timestamped JSON filename for a chat session, prefixed by CWD basename."""
    prefix = _sanitize_session_prefix(Path(cwd).name or "cwd")
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{prefix}_{stamp}.json"


def new_chat_session_path(cwd: Path) -> Path:
    """Return a new timestamped chat session path."""
    return get_chat_sessions_dir() / new_chat_session_filename(cwd)


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


def delete_chat_session(name: str) -> Optional[Path]:
    """
    Delete a saved chat session and remove it from the index.

    Accepts either a stem (no extension) or a full `*.json` filename.
    Returns the deleted session path on success, or None if not found.
    """
    name = str(name).strip()
    filename = name if name.endswith(".json") else f"{name}.json"
    path = resolve_chat_session_path(filename)
    if not path.is_file():
        return None
    try:
        path.unlink(missing_ok=True)
    except Exception:
        raise ValueError(f"Failed to delete session file: {path}")

    entries = _read_sessions_index()
    filtered = [entry for entry in entries if entry["filename"] != filename]
    filtered.sort(key=lambda item: item["filename"], reverse=True)
    _write_sessions_index(filtered)
    return path


def delete_all_chat_sessions() -> int:
    """
    Delete all saved session JSON files and clear the sessions index.

    Returns:
        Number of session files deleted.
    """
    entries = list_chat_sessions_index()
    deleted = 0
    for entry in entries:
        filename = str(entry.get("filename", "")).strip()
        if not filename:
            continue
        delete_chat_session(filename)
        deleted += 1
    return deleted


def ensure_session_index_row(session_path: Path, memory: MEMORY) -> None:
    """Ensure the sessions index includes this session filename."""
    filename = session_path.name
    entries = _read_sessions_index()
    if any(e.get("filename") == filename for e in entries):
        return

    user_msgs = memory.get_msgs(include=["user"], limit=-1, repr="list")
    first_prompt = ""
    if user_msgs:
        first_prompt = str(user_msgs[0].get("content", "")).strip()
    upsert_chat_session_index(filename=filename, first_prompt=first_prompt)


def save_chat_session(memory: MEMORY, session_path: Path) -> None:
    """Persist full ThoughtFlow MEMORY state to a session JSON file."""
    get_chat_sessions_dir()  # ensure dir exists
    memory.to_json(str(session_path), indent=2)


def load_latest_chat_session() -> tuple[Path, MEMORY] | None:
    """Load the newest session from the sessions index, if any."""
    entries = list_chat_sessions_index()
    if not entries:
        return None
    filename = str(entries[0].get("filename", "")).strip()
    if not filename:
        return None
    path = resolve_chat_session_path(filename)
    if not path.is_file():
        return None
    memory = MEMORY.from_json(str(path))
    return path, memory


def format_chat_sessions_list(limit: int = 50) -> list[str]:
    """Return display lines for `/sessions`."""
    entries = list_chat_sessions_index()
    if not entries:
        return ["(No Saved Sessions)"]
    lines: list[str] = []
    for entry in entries[:limit]:
        filename = str(entry.get("filename", "")).strip()
        stem = Path(filename).stem
        first_prompt = str(entry.get("first_prompt", "")).strip()
        suffix = f" - {first_prompt}" if first_prompt else ""
        lines.append(f"- {stem}{suffix}")
    return lines


def _choose_session_by_query(
    query: str, candidates: list[tuple[str, str]]
) -> tuple[str, str] | None:
    q = query.lower()
    exact = [c for c in candidates if c[0].lower() == q]
    if len(exact) == 1:
        return exact[0]
    starts = [c for c in candidates if c[0].lower().startswith(q)]
    if len(starts) == 1:
        return starts[0]
    contains = [c for c in candidates if q in c[0].lower()]
    if len(contains) == 1:
        return contains[0]
    return None


def match_chat_session(query: str) -> tuple[Path, list[str]] | None:
    """
    Try to match a session file by prefix/substring, git-SHA style.

    Returns:
        (path, []) on a unique match.
        None if no match or ambiguous; caller should use `match_chat_session_suggestions`.
    """
    query = str(query).strip()
    if not query:
        return None
    entries = list_chat_sessions_index()
    candidates: list[tuple[str, str]] = []
    for entry in entries:
        filename = str(entry.get("filename", "")).strip()
        if not filename:
            continue
        stem = Path(filename).stem
        candidates.append((stem, filename))

    chosen = _choose_session_by_query(query, candidates)
    if chosen is None:
        return None
    _stem, filename = chosen
    path = resolve_chat_session_path(filename)
    if not path.is_file():
        return None
    return path, []


def match_chat_session_suggestions(query: str, limit: int = 10) -> list[str]:
    """Return suggestion lines when a `/load` query is ambiguous or not found."""
    query = str(query).strip()
    entries = list_chat_sessions_index()
    candidates: list[tuple[str, str]] = []
    for entry in entries:
        filename = str(entry.get("filename", "")).strip()
        if not filename:
            continue
        stem = Path(filename).stem
        candidates.append((stem, filename))

    q = query.lower()
    exact = [c for c in candidates if c[0].lower() == q]
    starts = [c for c in candidates if c[0].lower().startswith(q)]
    contains = [c for c in candidates if q in c[0].lower()]
    matches = exact or starts or contains
    if not matches:
        return [f"No session matches: {query}"]
    lines = [f"Ambiguous session prefix: {query}"]
    for stem, _filename in matches[:limit]:
        lines.append(f"- {stem}")
    return lines
