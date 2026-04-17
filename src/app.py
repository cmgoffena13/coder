import argparse
import sys
from pathlib import Path

from thoughtflow import MEMORY

from src.internal.agent import CoderAgent
from src.internal.memory_utils import (
    delete_all_chat_sessions,
    ensure_session_index_row,
    load_latest_chat_session,
    new_chat_session_path,
    save_chat_session,
)
from src.internal.workspace import WorkspaceContext
from src.utils import get_version
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
        choices=("ask", "auto", "never"),
        default="auto",
        help="Approval policy for risky tools; auto grants the model arbitrary command execution and file writes.",
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
    /system - Show the system prompt
    /reset - Delete ALL saved sessions and start fresh
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
    session_path = new_chat_session_path()
    memory = MEMORY()
    if args.latest:
        loaded = load_latest_chat_session()
        if loaded is not None:
            session_path, memory = loaded
    print(build_welcome_message(agent, session_path.name))

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

        if user_input == "/reset":
            deleted = delete_all_chat_sessions()
            session_path = new_chat_session_path()
            memory = MEMORY()
            print(f"Reset: deleted {deleted} saved session(s).")
            print(build_welcome_message(agent, session_path.name))
            continue

        try:
            memory.add_msg("user", user_input)
            memory = agent(memory)
            print(memory.last_asst_msg(content_only=True))
            try:
                ensure_session_index_row(session_path, memory)
                save_chat_session(memory, session_path)
            except Exception as exc:
                print(f"Failed to save session: {exc}", file=sys.stderr)
        except RuntimeError as exc:
            print(str(exc), file=sys.stderr)
        except KeyboardInterrupt:
            print("\nGoodbye!")
            return 0


if __name__ == "__main__":
    raise SystemExit(main())
