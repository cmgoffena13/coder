from typing import Any

from thoughtflow import TOOL

from src.internal.parse.index_read import DiffLedger, index_read_report

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


def tool_index_read(
    workspace, ledger: DiffLedger, args: dict[str, Any], verbose: bool = False
):
    if verbose:
        print(f"[INDEX_READ INPUT] Path: {args.get('path', '')}")
    relative_path_arg = str(args.get("path", "")).strip()
    if not relative_path_arg:
        if verbose:
            print(f"[INDEX_READ ERROR]\n Path must not be empty.")
        raise ValueError("Path must not be empty")
    path = workspace.convert_relative_str_to_path(relative_path_arg)
    if not path.is_file():
        if verbose:
            print(f"[INDEX_READ ERROR]\n Path is not a file: {path}")
        raise ValueError("Path is not a file")

    relative_path = path.relative_to(workspace.root.resolve())
    tool_result = index_read_report(ledger, path, relative_path)

    if verbose:
        print(f"[INDEX_READ RESULT]\n{tool_result}\n")
    return tool_result


def add_index_read_tool(workspace, ledger: DiffLedger, verbose: bool = False) -> TOOL:
    return TOOL(
        name="index_read",
        description=(
            "Smart file read. Returns full content on first access; "
            "returns only the unified diff on re-reads within the same session. "
        ),
        parameters=index_read_parameters,
        fn=lambda **kwargs: tool_index_read(workspace, ledger, kwargs, verbose),
    )
