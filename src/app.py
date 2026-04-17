import sys
from pathlib import Path

from thoughtflow import MEMORY

from src.commands import (
    HELP_DETAILS,
    build_arg_parser,
    handle_delete_command,
    handle_load_command,
    handle_reset_command,
)
from src.internal.agent import CoderAgent
from src.internal.memory_utils import (
    ensure_session_index_row,
    format_chat_sessions_list,
    load_latest_chat_session,
    new_chat_session_path,
    save_chat_session,
)
from src.internal.parse.parser import index_workspace
from src.internal.workspace import WorkspaceContext
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


def main():
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
            loaded = handle_load_command(user_input, agent, args.cwd)
            if loaded is not None:
                session_path, memory = loaded
            continue

        if user_input.startswith("/delete"):
            handle_delete_command(user_input)
            continue

        if user_input == "/reset":
            session_path, memory = handle_reset_command(args.cwd, agent)
            continue

        # NOTE: Agent Loop
        try:
            memory.add_msg("user", user_input)
            memory = agent(memory)
            print(memory.last_asst_msg(content_only=True).lstrip())
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
