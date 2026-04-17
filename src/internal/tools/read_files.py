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


def tool_read_file(context, args):
    path = context.path(args["path"])
    if not path.is_file():
        raise ValueError("path is not a file")
    start = int(args.get("start", 1))
    end = int(args.get("end", 200))
    if start < 1 or end < start:
        raise ValueError("invalid line range")
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    body = "\n".join(
        f"{number:>4}: {line}"
        for number, line in enumerate(lines[start - 1 : end], start=start)
    )
    tool_result = f"# {path.relative_to(context.root)}\n{body}"
    return tool_result


def add_read_file_tool(context) -> TOOL:
    return TOOL(
        name="read_file",
        description="Read a UTF-8 file by line range.",
        parameters=read_file_parameters,
        fn=lambda **kwargs: tool_read_file(context, kwargs),
    )
