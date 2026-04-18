from dataclasses import dataclass, field
from pathlib import Path
from typing import List

from src.internal.parse.db import IndexDB
from src.internal.parse.languages.factory import AdapterFactory


@dataclass
class CallerInfo:
    file: str
    line: int
    context: str
    enclosing_test: str = ""


@dataclass
class ResolveResult:
    name: str
    kind: str
    file: str
    start_line: int
    end_line: int
    signature: str
    language: str
    source_code: str
    callers: List[CallerInfo] = field(default_factory=list)
    importers: List[str] = field(default_factory=list)
    tests: List[CallerInfo] = field(default_factory=list)
    git_last_modified: str = ""
    git_commit_hash: str = ""
    candidates: List[dict] = field(default_factory=list)


def _read_source_block(root: Path, filepath: Path, start: int, end: int) -> str:
    path = root / filepath
    if not path.is_file():
        return "(source unavailable — file missing on disk)"
    text = path.read_text(encoding="utf-8", errors="replace").splitlines()
    lo, hi = max(1, start), max(start, end)
    body: list[str] = []
    for i in range(lo - 1, min(hi, len(text))):
        body.append(f"{i + 1:>5}: {text[i]}")
    return "\n".join(body) if body else "(empty range)"


def _find_enclosing_test(db: IndexDB, caller_file: str, line: int) -> str:
    caller = Path(caller_file)
    adapter = AdapterFactory.get_adapter(caller)
    if adapter is None or not adapter.is_test_file(caller):
        return ""
    rows = db.execute(
        """
        SELECT name FROM symbols
        WHERE file = ? AND start_line <= ? AND end_line >= ?
          AND (name LIKE 'test_%' OR name LIKE 'Test%')
        ORDER BY start_line DESC
        LIMIT 1
        """,
        (caller_file, line, line),
    )
    return str(rows[0]["name"]) if rows else ""


def _dedupe_symbol_rows(rows) -> list:
    seen: set[tuple[str, str, int, int]] = set()
    out = []
    for r in rows:
        key = (str(r["name"]), str(r["file"]), int(r["start_line"]), int(r["end_line"]))
        if key in seen:
            continue
        seen.add(key)
        out.append(r)
    return out


def resolve_index(db: IndexDB, symbol_name: str, project_root: Path) -> ResolveResult:
    """
    Resolve a symbol: exact name, then case-insensitive, then partial (LIKE %%).
    Multiple definitions set ``candidates`` and default the first row.
    """
    rows = db.get_symbol(symbol_name)
    if not rows:
        rows = db.execute(
            "SELECT * FROM symbols WHERE name = ? COLLATE NOCASE "
            "ORDER BY file, start_line",
            (symbol_name,),
        )
    if not rows:
        rows = db.get_symbol_ilike(symbol_name)

    rows = _dedupe_symbol_rows(rows)

    if not rows:
        return ResolveResult(
            name=symbol_name,
            kind="unknown",
            file="",
            start_line=0,
            end_line=0,
            signature="",
            language="",
            source_code="",
        )

    if len(rows) > 1:
        candidates = [
            {
                "name": r["name"],
                "kind": r["kind"],
                "file": r["file"],
                "start_line": int(r["start_line"]),
            }
            for r in rows
        ]
        defn = rows[0]
    else:
        candidates = []
        defn = rows[0]

    root = project_root.resolve()
    source_code = _read_source_block(
        root,
        Path(str(defn["file"])),
        int(defn["start_line"]),
        int(defn["end_line"]),
    )

    sym_key_name = str(defn["name"])
    caller_rows = db.get_callers(sym_key_name)
    callers: list[CallerInfo] = []
    tests: list[CallerInfo] = []
    for row in caller_rows:
        enc = _find_enclosing_test(db, str(row["caller_file"]), int(row["line"]))
        ci = CallerInfo(
            file=str(row["caller_file"]),
            line=int(row["line"]),
            context=str(row["context"] or ""),
            enclosing_test=enc,
        )
        if enc:
            tests.append(ci)
        else:
            callers.append(ci)

    import_rows = db.get_importers(sym_key_name)
    importers = sorted({str(r["file"]) for r in import_rows})

    git_row = db.get_git_info(Path(str(defn["file"])))
    git_last_modified = str(git_row["last_modified"] or "") if git_row else ""
    git_commit_hash = str(git_row["last_commit_hash"] or "") if git_row else ""

    return ResolveResult(
        name=str(defn["name"]),
        kind=str(defn["kind"]),
        file=str(defn["file"]),
        start_line=int(defn["start_line"]),
        end_line=int(defn["end_line"]),
        signature=str(defn["signature"] or ""),
        language=str(defn["language"]),
        source_code=source_code,
        callers=callers,
        importers=importers,
        tests=tests,
        git_last_modified=git_last_modified,
        git_commit_hash=git_commit_hash,
        candidates=candidates,
    )


def format_resolve(result: ResolveResult) -> str:
    if result.kind == "unknown":
        return f'Symbol "{result.name}" not found in index.'

    lines: list[str] = [f"══ {result.name} ({result.kind}) ══"]
    lines.append(f"File:      {result.file}:{result.start_line}-{result.end_line}")
    lines.append(f"Language:  {result.language}")

    if result.git_commit_hash:
        short = result.git_commit_hash[:8]
        lines.append(f"Last edit: {result.git_last_modified}  [{short}]")

    lines.append("")
    lines.append("── Source ──")
    lines.append(result.source_code or "(source unavailable)")
    lines.append("")

    if result.callers:
        lines.append(f"── Called by ({len(result.callers)}) ──")
        for c in result.callers[:10]:
            ctx = c.context.strip()
            lines.append(f"  {c.file}:{c.line}  {ctx}")
        if len(result.callers) > 10:
            lines.append(f"  … and {len(result.callers) - 10} more")
        lines.append("")

    if result.tests:
        lines.append(f"── Tests ({len(result.tests)}) ──")
        for t in result.tests[:5]:
            ctx = t.context.strip()
            lines.append(f"  {t.file}:{t.line}  [{t.enclosing_test}]  {ctx}")
        lines.append("")

    if result.importers:
        lines.append(f"── Imported by ({len(result.importers)}) ──")
        for imp in result.importers[:8]:
            lines.append(f"  {imp}")
        lines.append("")

    if result.candidates:
        lines.append(f"── Multiple definitions found ({len(result.candidates)}) ──")
        lines.append(
            "  Showing first. Narrow the symbol or open the file you want, then resolve again."
        )
        for c in result.candidates:
            lines.append(f"  {c['file']}:{c['start_line']}  {c['name']}  ({c['kind']})")
        lines.append("")

    return "\n".join(lines).rstrip()


def index_resolve_report(db: IndexDB, project_root: Path, symbol_name: str) -> str:
    """Resolve ``symbol_name`` on ``db`` and return agent-facing text."""
    result = resolve_index(db, symbol_name, project_root)
    return format_resolve(result)
