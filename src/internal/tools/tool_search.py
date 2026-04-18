import shutil
import subprocess
from typing import Any

from thoughtflow import TOOL

search_parameters: dict[str, Any] = {
    "type": "object",
    "properties": {
        "pattern": {
            "type": "string",
            "description": "Search pattern (ripgrep/grep syntax).",
        },
        "path": {
            "type": "string",
            "description": "Directory or file path to search under (default: workspace root).",
            "default": ".",
        },
    },
    "required": ["pattern"],
}


def tool_search(workspace, args, verbose: bool = False):
    pattern = str(args.get("pattern", "")).strip()
    if not pattern:
        if verbose:
            print(f"[SEARCH ERROR]\n Pattern must not be empty")
        raise ValueError("Pattern must not be empty")
    path = workspace.path(args.get("path", "."))

    if shutil.which("rg"):
        result = subprocess.run(
            ["rg", "-n", "--smart-case", "--max-count", "200", pattern, str(path)],
            cwd=workspace.root,
            capture_output=True,
            text=True,
        )
        tool_result = result.stdout.strip() or result.stderr.strip() or "(no matches)"
    elif shutil.which("grep"):
        if verbose:
            print(f"[SEARCH] ripgrep not installed, defaulting to grep")
        result = subprocess.run(
            ["grep", "-n", "-m", "200", pattern, str(path)],
            cwd=workspace.root,
            capture_output=True,
            text=True,
        )
        tool_result = result.stdout.strip() or result.stderr.strip() or "(no matches)"
    else:
        tool_result = "(ripgrep and grep not installed; install ripgrep to use search)"
    if verbose:
        print(f"[SEARCH RESULT]\n {tool_result}")
    return tool_result


def add_search_tool(workspace, verbose: bool = False) -> TOOL:
    return TOOL(
        name="search",
        description="Search the workspace with ripgrep or grep as a fallback.",
        parameters=search_parameters,
        fn=lambda **kwargs: tool_search(workspace, kwargs, verbose),
    )
