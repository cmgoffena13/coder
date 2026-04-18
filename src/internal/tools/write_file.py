from typing import Any

from thoughtflow import TOOL

write_file_parameters: dict[str, Any] = {
    "type": "object",
    "properties": {
        "path": {
            "type": "string",
            "description": "File path relative to the workspace root.",
        },
        "content": {
            "type": "string",
            "description": "Full file contents to write (UTF-8).",
        },
    },
    "required": ["path", "content"],
}


def tool_write_file(workspace, args, verbose: bool = False):
    if verbose:
        print(
            f"[WRITE_FILE INPUT] Path: {args.get('path', '')}; Content: {args.get('content', '')}"
        )
    path = workspace.path(args["path"])
    content = str(args["content"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    tool_result = f"wrote {path.relative_to(workspace.root)} ({len(content)} chars)"
    if verbose:
        print(f"[WRITE_FILE RESULT]\n {tool_result}")
    return tool_result


def add_write_file_tool(workspace, verbose: bool = False) -> TOOL:
    return TOOL(
        name="write_file",
        description="Write a text file.",
        parameters=write_file_parameters,
        fn=lambda **kwargs: tool_write_file(workspace, kwargs, verbose),
    )
