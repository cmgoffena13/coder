import os
from pathlib import Path
from typing import Any

from thoughtflow import TOOL

from src.internal.git_utils import ignored_path_names_from_gitignore

_LIST_FILES_MAX_ENTRIES = 200
_LIST_FILES_MAX_DEPTH = 5

list_files_parameters: dict[str, Any] = {
    "type": "object",
    "properties": {
        "path": {
            "type": "string",
            "description": (
                "Directory path relative to the workspace root (default: current directory)."
            ),
            "default": ".",
        },
    },
    "required": [],
}


def tool_list_files(workspace, args, verbose: bool = False):
    if verbose:
        print(f"[LIST_FILES INPUT] Path: {args.get('path', '.')}")
    base = workspace.path(args.get("path", "."))
    if not base.is_dir():
        if verbose:
            print(f"[LIST_FILES ERROR]\n Path is not a directory: {base}")
        raise ValueError("Path is not a directory")

    root = workspace.root.resolve()
    base = base.resolve()
    ignore = ignored_path_names_from_gitignore(workspace.root)

    lines: list[str] = []

    def tree_prefix(depth: int) -> str:
        """depth 1 = direct child of listing root (one └─); deeper adds two spaces per level."""
        return ("  " * (depth - 1)) + "└─ " if depth > 0 else ""

    def walk_dir(directory: Path, dir_depth: int) -> None:
        if len(lines) >= _LIST_FILES_MAX_ENTRIES:
            return
        try:
            with os.scandir(directory) as it:
                entries = sorted(
                    it,
                    key=lambda e: (
                        e.is_file(follow_symlinks=False),
                        e.name.lower(),
                    ),
                )
        except OSError:
            return
        for entry in entries:
            if len(lines) >= _LIST_FILES_MAX_ENTRIES:
                return
            if entry.name in ignore:
                continue
            child_depth = dir_depth + 1
            if child_depth > _LIST_FILES_MAX_DEPTH:
                continue
            is_dir = entry.is_dir(follow_symlinks=False)
            kind = "[D]" if is_dir else "[F]"
            child = Path(entry)
            rel = child.relative_to(root)
            lines.append(f"{tree_prefix(child_depth)}{kind} {rel}")
            if is_dir and child_depth < _LIST_FILES_MAX_DEPTH:
                walk_dir(child, child_depth)

    walk_dir(base, 0)

    tool_result = "\n".join(lines) or "(empty)"
    if verbose:
        print(f"[LIST_FILES RESULT]\n{tool_result}\n")
    return tool_result


def add_list_files_tool(workspace, verbose: bool = False) -> TOOL:
    return TOOL(
        name="list_files",
        description=(
            "Tree-list files and directories under a path recursively (indents and └─ for nesting; "
            "This is a LAST RESORT tool. Use index_search or index_resolve instead."
            "max 5 levels below the path, 200 lines)."
        ),
        parameters=list_files_parameters,
        fn=lambda **kwargs: tool_list_files(workspace, kwargs, verbose),
    )
