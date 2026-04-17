from typing import Any

from thoughtflow import TOOL

patch_file_parameters: dict[str, Any] = {
    "type": "object",
    "properties": {
        "path": {
            "type": "string",
            "description": "File path relative to the workspace root.",
        },
        "old_text": {
            "type": "string",
            "description": "Exact text block to replace (must occur exactly once).",
        },
        "new_text": {
            "type": "string",
            "description": "Replacement text.",
        },
    },
    "required": ["path", "old_text", "new_text"],
}


def tool_patch_file(context, args):
    path = context.path(args["path"])
    if not path.is_file():
        raise ValueError("path is not a file")
    old_text = str(args.get("old_text", ""))
    if not old_text:
        raise ValueError("old_text must not be empty")
    if "new_text" not in args:
        raise ValueError("missing new_text")
    text = path.read_text(encoding="utf-8")
    count = text.count(old_text)
    if count != 1:
        raise ValueError(f"old_text must occur exactly once, found {count}")
    path.write_text(text.replace(old_text, str(args["new_text"]), 1), encoding="utf-8")
    tool_result = f"patched {path.relative_to(context.root)}"
    return tool_result


def add_patch_file_tool(context) -> TOOL:
    return TOOL(
        name="patch_file",
        description="Replace one exact text block in a file.",
        parameters=patch_file_parameters,
        fn=lambda **kwargs: tool_patch_file(context, kwargs),
    )
