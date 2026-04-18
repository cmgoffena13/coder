from typing import Any

from thoughtflow import TOOL

read_file_parameters: dict[str, Any] = {
    "type": "object",
    "properties": {
        "path": {
            "type": "string",
            "description": "File path relative to the workspace root.",
        },
        "start": {
            "type": "integer",
            "description": "First line number to include (1-based, default: 1).",
            "default": 1,
        },
        "end": {
            "type": "integer",
            "description": "Last line number to include (inclusive, default: 200).",
            "default": 200,
        },
    },
    "required": ["path"],
}


def tool_read_file(workspace, args, verbose: bool = False):
    if verbose:
        print(f"[READ_FILE INPUT] Path: {args.get('path', '')}")
    path = workspace.convert_relative_str_to_path(str(args["path"]).strip() or ".")
    if not path.is_file():
        if verbose:
            print(f"[READ_FILE ERROR]\n Path is not a file: {path}")
        raise ValueError("Path is not a file")
    start = int(args.get("start", 1))
    end = int(args.get("end", 200))
    if start < 1 or end < start:
        if verbose:
            print(f"[READ_FILE ERROR]\n Invalid line range")
        raise ValueError("Invalid line range")
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    body = "\n".join(
        f"{number:>4}: {line}"
        for number, line in enumerate(lines[start - 1 : end], start=start)
    )
    tool_result = f"# {path.relative_to(workspace.root)}\n{body}"
    if verbose:
        print(f"[READ_FILE RESULT]\n{tool_result}\n")
    return tool_result


def add_read_file_tool(workspace, verbose: bool = False) -> TOOL:
    return TOOL(
        name="read_file",
        description="Read a UTF-8 file by line range. This is a LAST RESORT tool. Use index_read or index_resolve instead.",
        parameters=read_file_parameters,
        fn=lambda **kwargs: tool_read_file(workspace, kwargs, verbose),
    )
