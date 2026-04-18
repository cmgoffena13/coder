import difflib
from typing import Any

from thoughtflow import TOOL

# (repo root str, normalized relative path) -> last emitted full snapshot for diff
_last_snapshots: dict[tuple[str, str], str] = {}

index_read_parameters: dict[str, Any] = {
    "type": "object",
    "properties": {
        "path": {
            "type": "string",
            "description": "File path relative to the workspace root.",
        },
    },
    "required": ["path"],
}


def tool_index_read(context, args, verbose: bool = False):
    rel = str(args.get("path", "")).strip()
    if not rel:
        if verbose:
            print(f"[INDEX_READ ERROR]\n Path must not be empty.")
        raise ValueError(f"Path must not be empty")
    path = context.path(rel)
    if not path.is_file():
        if verbose:
            print(f"[INDEX_READ ERROR]\n Path is not a file: {path}")
        raise ValueError("Path is not a file")

    root_key = str(context.root.resolve())
    rel_key = str(path.relative_to(context.root))
    key = (root_key, rel_key)

    text = path.read_text(encoding="utf-8", errors="replace")
    prev = _last_snapshots.get(key)

    if prev is None:
        _last_snapshots[key] = text
        header = f"# index_read (full): {rel_key}\n\n"
        tool_result = header + text
    else:
        a = prev.splitlines(keepends=True)
        b = text.splitlines(keepends=True)
        diff_lines = list(
            difflib.unified_diff(
                a,
                b,
                fromfile=f"{rel_key} (previous)",
                tofile=f"{rel_key} (current)",
                lineterm="",
            )
        )
        _last_snapshots[key] = text
        if not diff_lines:
            tool_result = f"# index_read (unchanged): {rel_key}\n\n(no changes)"
        else:
            tool_result = f"# index_read (diff): {rel_key}\n\n" + "\n".join(diff_lines)

    if verbose:
        print(f"[INDEX_READ RESULT]\n{tool_result[:2000]}")
    return tool_result


def add_index_read_tool(context, verbose: bool = False) -> TOOL:
    return TOOL(
        name="index_read",
        description=(
            "Smart file read. Returns full content on first access; "
            "returns only the unified diff on re-reads within the same session. "
            "Use INSTEAD of read_file."
        ),
        parameters=index_read_parameters,
        fn=lambda **kwargs: tool_index_read(context, kwargs, verbose),
    )
