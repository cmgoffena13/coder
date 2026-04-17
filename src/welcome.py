import shutil

from src.internal.agent import CoderAgent

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


def build_welcome_message(agent: CoderAgent, session_name: str):
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
            pair("APPROVAL", agent.approval_policy, "SESSION", session_name),
            row(""),
        ]
    )
    return "\n".join([border, *rows, border])
