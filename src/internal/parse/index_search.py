from dataclasses import dataclass
from typing import List

from src.internal.parse.db import IndexDB


@dataclass
class SearchResult:
    name: str
    kind: str
    file: str
    start_line: int
    end_line: int
    signature: str
    language: str
    rank: float
    call_context: str = ""
    call_line: int = 0
    call_caller_file: str = ""


def build_fts_match_query(query: str) -> str:
    """
    Turn natural language into an FTS5 MATCH expression.

    Digits are quoted (exact token); other words use prefix wildcard.
    Example: ``auth token 401`` → ``auth* OR token* OR "401"``.
    """
    words = query.strip().split()
    if not words:
        return ""
    terms: list[str] = []
    for w in words:
        clean = w.strip(".,;:!?\"'()[]{}").lower()
        if not clean:
            continue
        if clean.isdigit():
            terms.append(f'"{clean}"')
        else:
            terms.append(f"{clean}*")
    return " OR ".join(terms)


def search_index(db: IndexDB, query: str, limit: int = 15) -> List[SearchResult]:
    """
    Search symbols and call sites via FTS5, merge by definition where possible,
    and sort by BM25 rank (lower is better).
    """
    fts_query = build_fts_match_query(query)
    if not fts_query:
        return []

    results: dict[tuple, SearchResult] = {}

    try:
        sym_rows = db.search_symbols(fts_query, limit)
    except Exception:
        sym_rows = []

    for row in sym_rows:
        key = (row["file"], row["name"], row["start_line"])
        results[key] = SearchResult(
            name=row["name"],
            kind=row["kind"],
            file=row["file"],
            start_line=row["start_line"],
            end_line=row["end_line"],
            signature=row["signature"] or "",
            language=row["language"],
            rank=float(row["rank"]),
        )

    try:
        call_rows = db.search_calls(fts_query, limit)
    except Exception:
        call_rows = []

    for row in call_rows:
        sym_name = row["symbol_name"]
        sym_defs = db.get_symbol(sym_name)
        if sym_defs:
            defn = sym_defs[0]
            key = (defn["file"], defn["name"], defn["start_line"])
            ctx = row["context"] or ""
            caller = row["caller_file"]
            line = int(row["line"])
            if key not in results:
                results[key] = SearchResult(
                    name=defn["name"],
                    kind=defn["kind"],
                    file=defn["file"],
                    start_line=defn["start_line"],
                    end_line=defn["end_line"],
                    signature=defn["signature"] or "",
                    language=defn["language"],
                    rank=float(row["rank"]),
                    call_context=ctx,
                    call_line=line,
                    call_caller_file=caller,
                )
            elif not results[key].call_context:
                results[key].call_context = ctx
                results[key].call_line = line
                results[key].call_caller_file = caller
        else:
            key = (row["caller_file"], sym_name, row["line"])
            ctx = row["context"] or ""
            if key not in results:
                results[key] = SearchResult(
                    name=sym_name,
                    kind="call",
                    file=row["caller_file"],
                    start_line=int(row["line"]),
                    end_line=int(row["line"]),
                    signature=ctx,
                    language="",
                    rank=float(row["rank"]),
                    call_context=ctx,
                    call_line=int(row["line"]),
                    call_caller_file=row["caller_file"],
                )

    ordered = sorted(results.values(), key=lambda r: r.rank)
    return ordered[:limit]


def format_search(results: List[SearchResult], query: str) -> str:
    """Pretty-print merged search results grouped by file."""
    if not results:
        return f'No results for "{query}"'

    header = f'══ index search: "{query}" ({len(results)} results) ══\n'
    by_file: dict[str, list[SearchResult]] = {}
    for r in results:
        by_file.setdefault(r.file, []).append(r)

    lines = [header]
    for filepath, items in by_file.items():
        lines.append(filepath)
        for r in items:
            sig = r.signature.strip() if r.signature else r.name
            lines.append(f"  {sig:<60}  :{r.start_line}  {r.kind}")
            if r.call_context:
                loc = (
                    f"{r.call_caller_file}:{r.call_line}"
                    if r.call_caller_file
                    else f"line {r.call_line}"
                )
                lines.append(f"    └─ {loc}: {r.call_context.strip()}")
        lines.append("")

    return "\n".join(lines).rstrip()


def index_search_report(db: IndexDB, query: str, limit: int = 15) -> str:
    """Run FTS search on ``db`` and return the full agent-facing text (includes FTS line)."""
    fts_query = build_fts_match_query(query)
    results = search_index(db, fts_query, limit=limit)
    return format_search(results, query)
