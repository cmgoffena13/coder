from typing import Any

from thoughtflow import TOOL

from src.internal.parse.db import IndexDB
from src.internal.parse.index_resolve import index_resolve_report

index_resolve_parameters: dict[str, Any] = {
    "type": "object",
    "properties": {
        "symbol": {
            "type": "string",
            "description": "Exact or partial symbol name to resolve.",
        },
    },
    "required": ["symbol"],
}


def tool_index_resolve(workspace, args, verbose: bool = False):
    if verbose:
        print(f"[INDEX_RESOLVE INPUT] Symbol: {args.get('symbol', '')}")
    name = str(args.get("symbol", "")).strip()
    if not name:
        if verbose:
            print(f"[INDEX_RESOLVE ERROR]\n Symbol must not be empty.")
        raise ValueError("Symbol must not be empty")

    db = IndexDB(workspace.root)
    try:
        tool_result = index_resolve_report(db, workspace.root, name)
    finally:
        db.close()

    if verbose:
        print(f"[INDEX_RESOLVE RESULT]\n{tool_result}")
    return tool_result


def add_index_resolve_tool(workspace, verbose: bool = False) -> TOOL:
    return TOOL(
        name="index_resolve",
        description=(
            "Full context for a specific symbol: source code, every caller, "
            "every importer, related tests, and git history. "
            "Use INSTEAD of reading full files. "
            "Input: exact or partial symbol name from index_search results."
        ),
        parameters=index_resolve_parameters,
        fn=lambda **kwargs: tool_index_resolve(workspace, kwargs, verbose),
    )
