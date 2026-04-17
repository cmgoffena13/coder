import argparse
import sys
from pathlib import Path
from typing import Optional, Tuple

from thoughtflow import MEMORY

from src.internal.agent import CoderAgent
from src.internal.memory_utils import (
    delete_all_chat_sessions,
    delete_chat_session,
    match_chat_session,
    match_chat_session_suggestions,
    new_chat_session_path,
)
from src.settings import delete_all_parse_indexes
from src.welcome import build_welcome_message


def build_arg_parser():
    parser = argparse.ArgumentParser(description="Coder")
    parser.add_argument(
        "--version",
        action="store_true",
        help="Show CLI version",
    )
    parser.add_argument(
        "--info",
        action="store_true",
        help="Show CLI information",
    )
    parser.add_argument(
        "--cwd", type=Path, default=Path.cwd(), help="Current working directory"
    )
    parser.add_argument(
        "--approval",
        choices=("always", "balanced", "never"),
        default="balanced",
        help="Approval policy for risky tools. balanced prompts for approval-required tools.",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Verbose mode (print tool results)",
    )
    parser.add_argument(
        "-l",
        "--latest",
        action="store_true",
        help="Resume the most recent saved chat session",
    )
    return parser.parse_args()


HELP_DETAILS = """
Available Commands:
    /help - Show this help menu
    /sessions - List saved sessions
    /load <prefix> - Load a saved session (prefix match)
    /delete <name> - Delete a saved session (exact name match)
    /system - Show the system prompt
    /refresh - Full refresh of workspace index (parse all files)
    /reset - Delete ALL saved sessions, ALL repo indexes, and start fresh
    /exit - Exit the program
"""


def handle_load_command(
    user_input: str, agent: CoderAgent, _cwd: Path
) -> Optional[Tuple[Path, MEMORY]]:
    query = user_input.removeprefix("/load").strip()
    if not query:
        print("Usage: /load <prefix>")
        return None
    matched = match_chat_session(query)
    if matched is None:
        for line in match_chat_session_suggestions(query, limit=10):
            print(line)
        return None
    path, _notes = matched
    try:
        memory = MEMORY.from_json(str(path))
        session_path = path
    except Exception as exc:
        print(f"Failed to load session: {exc}", file=sys.stderr)
        return None
    print(f"Loaded session: {session_path.stem}")
    print(build_welcome_message(agent, session_path.stem))
    return session_path, memory


def handle_delete_command(user_input: str) -> None:
    name = user_input.removeprefix("/delete").strip()
    if not name:
        print("Usage: /delete <name>")
        return
    deleted_path = delete_chat_session(name)
    if deleted_path is None:
        print(f"No session named: {name}")
    else:
        print(f"Deleted session: {Path(deleted_path.name).stem}")


def handle_reset_command(cwd: Path, agent: CoderAgent) -> Tuple[Path, MEMORY]:
    deleted = delete_all_chat_sessions()
    indexes_removed = delete_all_parse_indexes()
    session_path = new_chat_session_path(cwd)
    memory = MEMORY()
    print(
        f"Reset: deleted {deleted} saved session(s) and "
        f"{indexes_removed} index database(s)."
    )
    print(build_welcome_message(agent, session_path.stem))
    return session_path, memory
