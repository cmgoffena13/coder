from typing import Any

from thoughtflow import TOOL

from src.internal.parse.db import IndexDB
from src.internal.parse.index_search import index_search_report

index_search_parameters: dict[str, Any] = {
    "type": "object",
    "properties": {
        "query": {
            "type": "string",
            "description": "Natural language or keyword search (FTS5 over symbols and call sites).",
        },
        "limit": {
            "type": "integer",
            "description": "Max merged results after ranking.",
            "default": 15,
        },
    },
    "required": ["query"],
}


def tool_index_search(workspace, args, verbose: bool = False):
    if verbose:
        print(
            f"[INDEX_SEARCH INPUT] Query: {args.get('query', '')}; Limit: {args.get('limit', 15)}"
        )
    query = str(args.get("query", "")).strip()
    if not query:
        if verbose:
            print(f"[INDEX_SEARCH ERROR]\n Query must not be empty.")
        raise ValueError("Query must not be empty")
    limit = max(1, min(50, int(args.get("limit", 15))))

    db = IndexDB(workspace.root)
    try:
        tool_result = index_search_report(db, query, limit=limit)
    finally:
        db.close()

    if verbose:
        print(f"[INDEX_SEARCH RESULT]\n{tool_result}\n")
    return tool_result


def add_index_search_tool(workspace, verbose: bool = False) -> TOOL:
    return TOOL(
        name="index_search",
        description=(
            "Search the codebase by keywords using FTS5 full-text search. "
            "Matches symbol names, signatures, file paths, and call-site context lines. "
            "Use this tool INSTEAD OF list_files. Use index_resolve to get detailed information about symbols."
            "Input: natural language query (e.g. 'auth token 401 unauthorized')."
        ),
        parameters=index_search_parameters,
        fn=lambda **kwargs: tool_index_search(workspace, kwargs, verbose),
    )
