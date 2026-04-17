import argparse
import sys
from pathlib import Path

from thoughtflow import MEMORY

from src.internal.agent import CoderAgent
from src.internal.memory_utils import (
    delete_all_chat_sessions,
    delete_chat_session,
    ensure_session_index_row,
    format_chat_sessions_list,
    load_latest_chat_session,
    match_chat_session,
    match_chat_session_suggestions,
    new_chat_session_path,
    save_chat_session,
)
from src.internal.parse.parser import index_workspace
from src.internal.workspace import WorkspaceContext
from src.settings import delete_all_parse_indexes
from src.utils import get_version
from src.welcome import build_welcome_message


def _refresh_code_index(
    workspace: WorkspaceContext, verbose: bool, full_refresh: bool = False
) -> None:
    try:
        stats = index_workspace(workspace.root, full_refresh=full_refresh)
        if verbose or full_refresh:
            print(
                f"[PARSER] Indexed {stats['files_indexed']} file(s), "
                f"{stats['symbols']} symbols, {stats['elapsed']:.2f}s"
            )
    except Exception as e:
        print(f"Code Index Update Failed: {e}", file=sys.stderr)


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
    /refresh - Full reindex of the workspace (parse all files)
    /reset - Delete ALL saved sessions, ALL repo indexes, and start fresh
    /exit - Exit the program
"""


def main(argv=None):
    args = build_arg_parser()
    if args.info:
        cli_path = Path(sys.argv[0]).resolve()
        print(f"CLI Path: {cli_path}")
        print(f"Config Directory: {Path.home() / '.config' / 'coder'}")
        return 0
    if args.version:
        print(f"Coder Version: {get_version()}")
        return 0

    workspace = WorkspaceContext.build(args.cwd)
    agent = CoderAgent(
        workspace=workspace, approval_policy=args.approval, verbose=args.verbose
    )
    _refresh_code_index(workspace, args.verbose)
    session_path = new_chat_session_path(args.cwd)
    memory = MEMORY()
    if args.latest:
        loaded = load_latest_chat_session()
        if loaded is not None:
            session_path, memory = loaded
    print(build_welcome_message(agent, session_path.stem))

    while True:
        try:
            user_input = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            return 0

        if user_input == "/help":
            print(HELP_DETAILS)
            continue

        if user_input == "/exit":
            return 0

        if user_input == "/system":
            print(agent.system_prompt)
            continue

        if user_input == "/refresh":
            _refresh_code_index(workspace, args.verbose, full_refresh=True)
            continue

        if user_input == "/sessions":
            for line in format_chat_sessions_list(limit=50):
                print(line)
            continue

        if user_input.startswith("/load"):
            query = user_input.removeprefix("/load").strip()
            if not query:
                print("Usage: /load <prefix>")
                continue
            matched = match_chat_session(query)
            if matched is None:
                for line in match_chat_session_suggestions(query, limit=10):
                    print(line)
                continue
            path, _notes = matched
            try:
                memory = MEMORY.from_json(str(path))
                session_path = path
            except Exception as exc:
                print(f"Failed to load session: {exc}", file=sys.stderr)
                continue
            print(f"Loaded session: {session_path.stem}")
            print(build_welcome_message(agent, session_path.stem))
            continue

        if user_input.startswith("/delete"):
            name = user_input.removeprefix("/delete").strip()
            if not name:
                print("Usage: /delete <name>")
                continue
            deleted_path = delete_chat_session(name)
            if deleted_path is None:
                print(f"No session named: {name}")
            else:
                print(f"Deleted session: {Path(deleted_path.name).stem}")
            continue

        if user_input == "/reset":
            deleted = delete_all_chat_sessions()
            indexes_removed = delete_all_parse_indexes()
            session_path = new_chat_session_path(args.cwd)
            memory = MEMORY()
            print(
                f"Reset: deleted {deleted} saved session(s) and "
                f"{indexes_removed} index database(s)."
            )
            print(build_welcome_message(agent, session_path.stem))
            continue

        try:
            memory.add_msg("user", user_input)
            memory = agent(memory)
            print(memory.last_asst_msg(content_only=True))
            _refresh_code_index(workspace, args.verbose)
            try:
                ensure_session_index_row(session_path, memory)
                save_chat_session(memory, session_path)
            except Exception as e:
                print(f"Failed to save session: {e}", file=sys.stderr)
        except RuntimeError as e:
            print(str(e), file=sys.stderr)
        except KeyboardInterrupt:
            print("\nGoodbye!")
            return 0


if __name__ == "__main__":
    raise SystemExit(main())
