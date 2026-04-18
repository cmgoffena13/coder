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


def tool_patch_file(workspace, args, verbose: bool = False):
    if verbose:
        print(f"[PATCH_FILE INPUT] Path: {args.get('path', '')}")
    path = workspace.path(args["path"])
    if not path.is_file():
        if verbose:
            print(f"[PATCH_FILE ERROR]\n Path is not a file: {path}")
        raise ValueError("Path is not a file")
    old_text = str(args.get("old_text", ""))
    if not old_text:
        if verbose:
            print(f"[PATCH_FILE ERROR]\n Old_text must not be empty")
        raise ValueError("Old_text must not be empty")
    if "new_text" not in args:
        if verbose:
            print(f"[PATCH_FILE ERROR]\n Missing new_text")
        raise ValueError("Missing new_text")
    text = path.read_text(encoding="utf-8")
    count = text.count(old_text)
    if count != 1:
        if verbose:
            print(
                f"[PATCH_FILE ERROR]\n Old_text must occur exactly once, found {count}"
            )
        raise ValueError(f"Old_text must occur exactly once, found {count}")
    path.write_text(text.replace(old_text, str(args["new_text"]), 1), encoding="utf-8")
    tool_result = f"patched {path.relative_to(workspace.root)}"
    if verbose:
        print(f"[PATCH_FILE RESULT]\n {tool_result}")
    return tool_result


def add_patch_file_tool(workspace, verbose: bool = False) -> TOOL:
    return TOOL(
        name="patch_file",
        description="Replace one exact text block in a file.",
        parameters=patch_file_parameters,
        fn=lambda **kwargs: tool_patch_file(workspace, kwargs, verbose),
    )
