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


def tool_run_shell(workspace, args, verbose: bool = False):
    if verbose:
        print(
            f"[RUN_SHELL INPUT] Command: {args.get('command', '')}; Timeout: {args.get('timeout', 20)}"
        )
    command = str(args.get("command", "")).strip()
    if not command:
        if verbose:
            print(f"[RUN_SHELL ERROR]\n Command must not be empty")
        raise ValueError("Command must not be empty")
    timeout = int(args.get("timeout", 20))
    if timeout < 1 or timeout > 120:
        if verbose:
            print(f"[RUN_SHELL ERROR]\n Timeout must be in [1, 120]")
        raise ValueError("Timeout must be in [1, 120]")
    result = subprocess.run(
        command,
        cwd=workspace.root,
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
    if verbose:
        print(f"[RUN_SHELL RESULT]\n {tool_result}")
    return tool_result


def add_run_shell_tool(workspace, verbose: bool = False) -> TOOL:
    return TOOL(
        name="run_shell",
        description="Run a shell command in the repo root.",
        parameters=run_shell_parameters,
        fn=lambda **kwargs: tool_run_shell(workspace, kwargs, verbose),
    )
