import re
from typing import Any

from thoughtflow import TOOL

from src.internal.parse.db import IndexDB

_WORD_RE = re.compile(r"[A-Za-z0-9_]+")


def _fts_or_terms(natural_query: str) -> str:
    """Turn a loose phrase into an FTS5 OR expression (token-wise)."""
    raw = str(natural_query).strip()
    if not raw:
        return ""
    tokens = [t for t in _WORD_RE.findall(raw) if len(t) > 1]
    if not tokens:
        return raw
    return " OR ".join(tokens)


index_search_parameters: dict[str, Any] = {
    "type": "object",
    "properties": {
        "query": {
            "type": "string",
            "description": "Natural language or keyword search (FTS5 over symbols and call sites).",
        },
        "limit": {
            "type": "integer",
            "description": "Max rows per category (symbols / calls).",
            "default": 15,
        },
    },
    "required": ["query"],
}


def tool_index_search(context, args, verbose: bool = False):
    q = str(args.get("query", "")).strip()
    if not q:
        if verbose:
            print(f"[INDEX_SEARCH ERROR]\n Query must not be empty.")
        raise ValueError("Query must not be empty")
    limit = max(1, min(50, int(args.get("limit", 15))))
    fts = _fts_or_terms(q)
    if not fts:
        if verbose:
            print(f"[INDEX_SEARCH ERROR]\n Query has no searchable tokens.")
        raise ValueError("Query has no searchable tokens")

    lines: list[str] = [f"# index_search: {q!r}", f"(FTS: {fts!r})", ""]

    db = IndexDB(context.root)
    try:
        sym_rows = db.search_symbols(fts, limit=limit)
        call_rows = db.search_calls(fts, limit=limit)

        lines.append("## Symbols")
        if not sym_rows:
            lines.append("(none)")
        else:
            for r in sym_rows:
                sig = r["signature"] or ""
                sig_s = f" — {sig}" if sig else ""
                lines.append(
                    f"- {r['name']} ({r['kind']}) @ {r['file']}:{r['start_line']}{sig_s}"
                )

        lines.append("")
        lines.append("## Call sites")
        if not call_rows:
            lines.append("(none)")
        else:
            for r in call_rows:
                ctx = (r["context"] or "").strip()
                ctx_s = f" — {ctx}" if ctx else ""
                lines.append(
                    f"- {r['symbol_name']} @ {r['caller_file']}:{r['line']}{ctx_s}"
                )
    finally:
        db.close()

    tool_result = "\n".join(lines)
    if verbose:
        print(f"[INDEX_SEARCH RESULT]\n{tool_result}")
    return tool_result


def add_index_search_tool(context, verbose: bool = False) -> TOOL:
    return TOOL(
        name="index_search",
        description=(
            "Search the codebase by keywords using FTS5 full-text search. "
            "Use BEFORE running ripgrep or grep. Matches symbol names, signatures, "
            "file paths, and call-site context lines. "
            "Input: natural language query (e.g. 'auth token 401 unauthorized')."
        ),
        parameters=index_search_parameters,
        fn=lambda **kwargs: tool_index_search(context, kwargs, verbose),
    )
