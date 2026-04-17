from typing import Any

from thoughtflow import TOOL

IGNORED_PATH_NAMES = {
    ".git",
    ".idea",
    ".vscode",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "venv",
    ".env",
}

list_files_parameters: dict[str, Any] = {
    "type": "object",
    "properties": {
        "path": {
            "type": "string",
            "description": "Directory path relative to the workspace root (default: current directory).",
            "default": ".",
        },
    },
    "required": [],
}


def tool_list_files(context, args):
    path = context.path(args.get("path", "."))
    if not path.is_dir():
        raise ValueError("path is not a directory")
    entries = [
        item
        for item in sorted(
            path.iterdir(), key=lambda item: (item.is_file(), item.name.lower())
        )
        if item.name not in IGNORED_PATH_NAMES
    ]
    lines = []
    for entry in entries[:200]:
        kind = "[D]" if entry.is_dir() else "[F]"
        lines.append(f"{kind} {entry.relative_to(context.root)}")
    tool_result = "\n".join(lines) or "(empty)"
    return tool_result


def add_list_files_tool(context) -> TOOL:
    return TOOL(
        name="list_files",
        description="List files in the workspace.",
        parameters=list_files_parameters,
        fn=lambda **kwargs: tool_list_files(context, kwargs),
    )
