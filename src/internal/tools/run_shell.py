import subprocess
from typing import Any

from thoughtflow import TOOL

run_shell_parameters: dict[str, Any] = {
    "type": "object",
    "properties": {
        "command": {
            "type": "string",
            "description": "Shell command to run in the repo root.",
        },
        "timeout": {
            "type": "integer",
            "description": "Timeout in seconds (1–120, default: 20).",
            "default": 20,
        },
    },
    "required": ["command"],
}


def tool_run_shell(context, args):
    command = str(args.get("command", "")).strip()
    if not command:
        raise ValueError("command must not be empty")
    timeout = int(args.get("timeout", 20))
    if timeout < 1 or timeout > 120:
        raise ValueError("timeout must be in [1, 120]")
    result = subprocess.run(
        command,
        cwd=context.root,
        shell=True,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    tool_result = "\n".join(
        [
            f"exit_code: {result.returncode}",
            "stdout:",
            result.stdout.strip() or "(empty)",
            "stderr:",
            result.stderr.strip() or "(empty)",
        ]
    )
    return tool_result


def add_run_shell_tool(context) -> TOOL:
    return TOOL(
        name="run_shell",
        description="Run a shell command in the repo root.",
        parameters=run_shell_parameters,
        fn=lambda **kwargs: tool_run_shell(context, kwargs),
    )
