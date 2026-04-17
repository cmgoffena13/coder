import argparse
import shutil
import sys
from pathlib import Path

from thoughtflow import MEMORY

from src.internal.agent import CoderAgent
from src.internal.workspace import WorkspaceContext

# fmt: off
LOGO = r"""                                                         
_________            .___            
\_   ___ \  ____   __| _/___________ 
/    \  \/ /  _ \ / __ |/ __ \_  __ \
\     \___(  <_> ) /_/ \  ___/|  | \/
 \______  /\____/\____ |\___  >__|   
        \/            \/    \/     
"""
# fmt: on


def middle(text, limit):
    text = str(text).replace("\n", " ")
    if len(text) <= limit:
        return text
    if limit <= 3:
        return text[:limit]
    left = (limit - 3) // 2
    right = limit - 3 - left
    return text[:left] + "..." + text[-right:]


def build_welcome_message(agent: CoderAgent):
    width = max(68, min(shutil.get_terminal_size((80, 20)).columns, 84))
    inner = width - 4
    gap = 3
    left_width = (inner - gap) // 2
    right_width = inner - gap - left_width

    def row(text):
        body = middle(text, width - 4)
        return f"| {body.ljust(width - 4)} |"

    def divider(char: str):
        return "+" + char * (width - 2) + "+"

    def center(text):
        body = middle(text, inner)
        return f"| {body.center(inner)} |"

    def cell(label, value, size):
        body = middle(f"{label:<9} {value}", size)
        return body.ljust(size)

    def pair(left_label, left_value, right_label, right_value):
        left = cell(left_label, left_value, left_width)
        right = cell(right_label, right_value, right_width)
        return f"| {left}{' ' * gap}{right} |"

    border = divider("=")
    llm = agent.llm
    model_display = f"{llm.model}" if llm is not None else "?"
    rows = [center(logo_line) for logo_line in LOGO.splitlines() if logo_line.strip()]
    rows.extend(
        [
            row(""),
            center("LOCAL CODING AGENT"),
            divider("-"),
            row(""),
            row("WORKSPACE  " + middle(agent.workspace.cwd, inner - 11)),
            pair(
                "MODEL",
                model_display,
                "BRANCH",
                agent.workspace.branch,
            ),
            pair("APPROVAL", agent.approval_policy, "SESSION", "none"),
            row(""),
        ]
    )
    return "\n".join([border, *rows, border])


def build_arg_parser():
    parser = argparse.ArgumentParser(description="Coder")
    parser.add_argument(
        "--cwd", type=Path, default=Path.cwd(), help="Current working directory"
    )
    parser.add_argument(
        "--approval",
        choices=("ask", "auto", "never"),
        default="ask",
        help="Approval policy for risky tools; auto grants the model arbitrary command execution and file writes.",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Verbose mode (print tool results)",
    )
    return parser.parse_args()


HELP_DETAILS = """
Available Commands:
    /help - Show this help menu
    /system - Show the system prompt
    /exit - Exit the program
"""


def main(argv=None):
    args = build_arg_parser()
    workspace = WorkspaceContext.build(args.cwd)
    agent = CoderAgent(
        workspace=workspace, approval_policy=args.approval, verbose=args.verbose
    )
    memory = MEMORY()
    print(build_welcome_message(agent))

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

        try:
            memory.add_msg("user", user_input)
            memory = agent(memory)
            print("\n")
            print(memory.last_asst_msg(content_only=True))
        except RuntimeError as exc:
            print(str(exc), file=sys.stderr)
        except KeyboardInterrupt:
            print("\nGoodbye!")
            return 0


if __name__ == "__main__":
    raise SystemExit(main())
