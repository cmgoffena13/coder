from typing import Any

from thoughtflow import TOOL

from src.utils import ignored_path_names_from_gitignore

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


def tool_list_files(context, args, verbose: bool = False):
    path = context.path(args.get("path", "."))
    if not path.is_dir():
        if verbose:
            print(f"[LIST_FILES ERROR]\n Path is not a directory: {path}")
        raise ValueError("Path is not a directory")
    entries = [
        item
        for item in sorted(
            path.iterdir(), key=lambda item: (item.is_file(), item.name.lower())
        )
        if item.name not in ignored_path_names_from_gitignore(context.root)
    ]
    lines = []
    for entry in entries[:200]:
        kind = "[D]" if entry.is_dir() else "[F]"
        lines.append(f"{kind} {entry.relative_to(context.root)}")
    tool_result = "\n".join(lines) or "(empty)"
    if verbose:
        print(f"[LIST_FILES RESULT]\n {tool_result}")
    return tool_result


def add_list_files_tool(context, verbose: bool = False) -> TOOL:
    return TOOL(
        name="list_files",
        description="List files in the workspace.",
        parameters=list_files_parameters,
        fn=lambda **kwargs: tool_list_files(context, kwargs, verbose),
    )
