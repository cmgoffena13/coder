from typing import Any

from thoughtflow import TOOL

from src.internal.parse.db import IndexDB

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


def _read_lines(root, rel_file: str, start: int, end: int) -> str:
    path = root / rel_file
    if not path.is_file():
        return "(file missing on disk)"
    text = path.read_text(encoding="utf-8", errors="replace").splitlines()
    lo, hi = max(1, start), max(start, end)
    body = []
    for i in range(lo - 1, min(hi, len(text))):
        body.append(f"{i + 1:>5}: {text[i]}")
    return "\n".join(body) if body else "(empty range)"


def tool_index_resolve(context, args, verbose: bool = False):
    name = str(args.get("symbol", "")).strip()
    if not name:
        if verbose:
            print(f"[INDEX_RESOLVE ERROR]\n Symbol must not be empty.")
        raise ValueError("Symbol must not be empty")

    lines: list[str] = [f"# index_resolve: {name!r}", ""]

    db = IndexDB(context.root)
    try:
        rows = db.get_symbol_ilike(name)
        if not rows:
            lines.append("No indexed symbols matched.")
            tool_result = "\n".join(lines)
            if verbose:
                print(f"[INDEX_RESOLVE RESULT]\n{tool_result}")
            return tool_result

        seen: set[tuple[str, str, int, int]] = set()
        unique_rows = []
        for row in rows:
            key = (row["name"], row["file"], row["start_line"], row["end_line"])
            if key in seen:
                continue
            seen.add(key)
            unique_rows.append(row)

        for index, row in enumerate(unique_rows[:12]):
            if index > 0:
                lines.append("")
            sym_name = row["name"]
            rel = row["file"]
            sl, el = int(row["start_line"]), int(row["end_line"])
            lines.append(f"## {sym_name} ({row['kind']}) — {rel}:{sl}-{el}")
            if row["signature"]:
                lines.append(f"Signature: {row['signature']}")
            lines.append("```")
            lines.append(_read_lines(context.root, rel, sl, el))
            lines.append("```")

            git = db.get_git_info(rel)
            if git and (git["last_commit_hash"] or git["last_modified"]):
                lines.append(
                    f"Git: {git['last_commit_hash'] or '?'} @ {git['last_modified'] or '?'}"
                )

            callers = db.get_callers(sym_name)
            if callers:
                lines.append("### Callers")
                for caller in callers[:40]:
                    caller_file = caller["caller_file"]
                    note = " [test]" if "test" in caller_file.lower() else ""
                    caller_ctx = (caller["context"] or "").strip()
                    extra = f" — {caller_ctx}" if caller_ctx else ""
                    lines.append(f"- {caller_file}:{caller['line']}{note}{extra}")
                if len(callers) > 40:
                    lines.append(f"... and {len(callers) - 40} more")

            importers = db.get_importers(sym_name)
            if importers:
                lines.append("### Importers")
                for importer in importers[:30]:
                    import_line = importer["import_line"] or ""
                    lines.append(
                        f"- {importer['file']}"
                        + (f": {import_line}" if import_line else "")
                    )
                if len(importers) > 30:
                    lines.append(f"... and {len(importers) - 30} more")

        if len(unique_rows) > 12:
            lines.append("")
            lines.append(f"(truncated: {len(unique_rows)} matches, showing first 12)")
    finally:
        db.close()

    tool_result = "\n".join(lines)
    if verbose:
        print(f"[INDEX_RESOLVE RESULT]\n{tool_result}")
    return tool_result


def add_index_resolve_tool(context, verbose: bool = False) -> TOOL:
    return TOOL(
        name="index_resolve",
        description=(
            "Full context for a specific symbol: source code, every caller, "
            "every importer, related tests, and git history. "
            "Use INSTEAD of reading full files. "
            "Input: exact or partial symbol name from index_search results."
        ),
        parameters=index_resolve_parameters,
        fn=lambda **kwargs: tool_index_resolve(context, kwargs, verbose),
    )
