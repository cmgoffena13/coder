import re
from typing import Any

from thoughtflow import TOOL

from src.internal.parse.db import IndexDB
from src.utils import loads_json_list

index_task_memory_parameters: dict[str, Any] = {
    "type": "object",
    "properties": {
        "query": {
            "type": "string",
            "description": "Current task or question to match against past indexed tasks.",
        },
        "threshold": {
            "type": "number",
            "description": "Minimum Jaccard similarity on token sets (0-1).",
            "default": 0.25,
        },
    },
    "required": ["query"],
}


def tool_index_task_memory(workspace, args, verbose: bool = False):
    if verbose:
        print(
            f"[INDEX_TASK_MEMORY INPUT] Query: {args.get('query', '')}; Threshold: {args.get('threshold', 0.25)}"
        )
    q = str(args.get("query", "")).strip()
    if not q:
        if verbose:
            print(f"[INDEX_TASK_MEMORY ERROR]\n Query must not be empty.")
        raise ValueError("query must not be empty")
    threshold = float(args.get("threshold", 0.25))
    threshold = max(0.0, min(1.0, threshold))

    _word = re.compile(r"[A-Za-z0-9_]+")

    def task_similarity(task_text: str) -> float:
        def token_set(s: str) -> set[str]:
            return {t.lower() for t in _word.findall(s) if len(t) > 1}

        a, b = token_set(q), token_set(task_text)
        if not a or not b:
            return 0.0
        return len(a & b) / len(a | b)

    lines: list[str] = ["# index_memory", ""]

    db = IndexDB(workspace.root)
    try:
        rows = db.get_all_session_embeddings()
    finally:
        db.close()

    if not rows:
        lines.append(
            "No rows in session_memory (nothing recorded yet). "
            "Proceed with index_search / index_resolve."
        )
        tool_result = "\n".join(lines)
        if verbose:
            print(f"[INDEX_TASK_MEMORY RESULT]\n{tool_result}")
        return tool_result

    best = None
    best_score = -1.0
    for r in rows:
        task = str(r["task_text"] or "")
        score = task_similarity(task)
        if score > best_score:
            best_score = score
            best = r

    if best is None or best_score < threshold:
        lines.append(
            f"No memory match above threshold {threshold:.2f} "
            f"(best was {best_score:.2f}). Proceed with index_search."
        )
        tool_result = "\n".join(lines)
        if verbose:
            print(f"[INDEX_TASK_MEMORY RESULT]\n{tool_result}")
        return tool_result

    files = loads_json_list(best["context_files"])
    syms = loads_json_list(best["context_symbols"])

    lines.append(f"[Memory match — similarity {best_score:.2f}]")
    lines.append(f"Past task: {best['task_text']}")
    lines.append("")
    lines.append(f"Files ({len(files)}):")
    for f in files[:50]:
        lines.append(f"  {f}")
    if len(files) > 50:
        lines.append(f"  ... ({len(files) - 50} more)")
    if syms:
        lines.append("")
        lines.append(f"Symbols ({len(syms)}):")
        for s in syms[:50]:
            lines.append(f"  {s}")
        if len(syms) > 50:
            lines.append(f"  ... ({len(syms) - 50} more)")

    tool_result = "\n".join(lines)
    if verbose:
        print(f"[INDEX_TASK_MEMORY RESULT]\n{tool_result}")
    return tool_result


def add_index_task_memory_tool(workspace, verbose: bool = False) -> TOOL:
    return TOOL(
        name="index_task_memory",
        description=(
            "Check if a similar task was completed in a past session. "
            "Call this FIRST, before any search or resolve. "
            "If a match is found, use the returned context set directly — "
            "skip search and resolve entirely. "
            "Input: the user's current question or task description."
        ),
        parameters=index_task_memory_parameters,
        fn=lambda **kwargs: tool_index_task_memory(workspace, kwargs, verbose),
    )
