from functools import lru_cache
from pathlib import Path
from typing import Any

from thoughtflow import TOOL


@lru_cache()
def ignored_path_names_from_gitignore(repo_root: Path) -> set[str]:
    """
    Return a cached set of *entry names* to ignore, derived from `.gitignore`.

    Note: `.gitignore` supports complex patterns; this helper intentionally only
    extracts simple basename-style ignores (e.g. `.venv`, `dist`, `__pycache__`).
    """
    always_ignore = {".git", ".gitignore"}
    gitignore_path = repo_root / ".gitignore"
    if not gitignore_path.is_file():
        return always_ignore

    ignored: set[str] = set(always_ignore)
    for raw in gitignore_path.read_text(
        encoding="utf-8", errors="replace"
    ).splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("!"):
            continue
        line = line.removesuffix("/")
        line = line.lstrip("/")
        if any(ch in line for ch in ("*", "?", "[", "]")):
            continue
        if "/" in line:
            continue
        ignored.add(line)
    return ignored


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
