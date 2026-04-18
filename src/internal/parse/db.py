import hashlib
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from sqlite3 import Row
from typing import Any, List, Optional

from src.settings import get_index_storage_dir


@dataclass
class IndexBatchItem:
    """One file's index payload for :meth:`IndexDB.apply_index_batch`."""

    filepath: str
    content_hash: str
    language: str
    line_count: int
    symbols: List[Any]
    calls: List[Any]
    imports: List[Any]
    git_last_modified: Optional[str] = None
    git_commit_hash: Optional[str] = None


_SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;

CREATE TABLE IF NOT EXISTS symbols (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    kind TEXT NOT NULL,
    file TEXT NOT NULL,
    start_line INTEGER NOT NULL,
    end_line INTEGER NOT NULL,
    signature TEXT,
    language TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS calls (
    id INTEGER PRIMARY KEY,
    symbol_name TEXT NOT NULL,
    caller_file TEXT NOT NULL,
    line INTEGER NOT NULL,
    context TEXT,
    full_name TEXT
);

CREATE TABLE IF NOT EXISTS imports (
    id INTEGER PRIMARY KEY,
    symbol_name TEXT NOT NULL,
    file TEXT NOT NULL,
    import_line TEXT
);

CREATE TABLE IF NOT EXISTS file_meta (
    file TEXT PRIMARY KEY,
    content_hash TEXT NOT NULL,
    last_indexed REAL,
    language TEXT,
    line_count INTEGER
);

CREATE TABLE IF NOT EXISTS git_info (
    file TEXT PRIMARY KEY,
    last_modified TEXT,
    last_commit_hash TEXT
);

CREATE VIRTUAL TABLE IF NOT EXISTS symbols_fts USING fts5(
    name,
    kind,
    file,
    signature,
    content=symbols,
    content_rowid=id
);

CREATE TRIGGER IF NOT EXISTS symbols_ai AFTER INSERT ON symbols BEGIN
    INSERT INTO symbols_fts(rowid, name, kind, file, signature)
    VALUES (new.id, new.name, new.kind, new.file, new.signature);
END;

CREATE TRIGGER IF NOT EXISTS symbols_ad AFTER DELETE ON symbols BEGIN
    INSERT INTO symbols_fts(symbols_fts, rowid, name, kind, file, signature)
    VALUES ('delete', old.id, old.name, old.kind, old.file, old.signature);
END;

CREATE TRIGGER IF NOT EXISTS symbols_au AFTER UPDATE ON symbols BEGIN
    INSERT INTO symbols_fts(symbols_fts, rowid, name, kind, file, signature)
    VALUES ('delete', old.id, old.name, old.kind, old.file, old.signature);
    INSERT INTO symbols_fts(rowid, name, kind, file, signature)
    VALUES (new.id, new.name, new.kind, new.file, new.signature);
END;

CREATE VIRTUAL TABLE IF NOT EXISTS calls_fts USING fts5(
    symbol_name,
    caller_file,
    context,
    content=calls,
    content_rowid=id
);

CREATE TRIGGER IF NOT EXISTS calls_ai AFTER INSERT ON calls BEGIN
    INSERT INTO calls_fts(rowid, symbol_name, caller_file, context)
    VALUES (new.id, new.symbol_name, new.caller_file, new.context);
END;

CREATE TRIGGER IF NOT EXISTS calls_ad AFTER DELETE ON calls BEGIN
    INSERT INTO calls_fts(calls_fts, rowid, symbol_name, caller_file, context)
    VALUES ('delete', old.id, old.symbol_name, old.caller_file, old.context);
END;

CREATE INDEX IF NOT EXISTS idx_symbols_name ON symbols(name);
CREATE INDEX IF NOT EXISTS idx_symbols_file ON symbols(file);
CREATE INDEX IF NOT EXISTS idx_calls_name   ON calls(symbol_name);
CREATE INDEX IF NOT EXISTS idx_imports_name ON imports(symbol_name);
"""


class IndexDB:
    def __init__(self, workspace_root: Path):
        self.path = workspace_root.resolve()
        key = hashlib.sha256(str(self.path).encode()).hexdigest()[:24]
        self._db_file = get_index_storage_dir() / f"{key}.sqlite"
        self._conn = sqlite3.connect(str(self._db_file), check_same_thread=False)
        self._conn.row_factory = Row
        self._apply_schema()

    def close(self) -> None:
        self._conn.close()

    def _apply_schema(self):
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def execute(self, sql: str, params: tuple = ()) -> List[Row]:
        cur = self._conn.execute(sql, params)
        return cur.fetchall()

    def is_stale(self, filepath: Path, content_hash: str) -> bool:
        rows = self.execute(
            "SELECT content_hash FROM file_meta WHERE file = ?", (str(filepath),)
        )
        if not rows:
            return True
        return rows[0]["content_hash"] != content_hash

    def _write_file_index_unlocked(
        self,
        filepath: Path,
        content_hash: str,
        language: str,
        line_count: int,
        symbols,
        calls,
        imports,
    ) -> None:
        """Replace index rows for one file; caller must hold an open transaction."""
        key = str(filepath)
        self._conn.execute("DELETE FROM symbols WHERE file = ?", (key,))
        self._conn.execute("DELETE FROM calls WHERE caller_file = ?", (key,))
        self._conn.execute("DELETE FROM imports WHERE file = ?", (key,))

        self._conn.executemany(
            "INSERT INTO symbols (name, kind, file, start_line, end_line, signature, language) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    s.name,
                    s.kind,
                    key,
                    s.start_line,
                    s.end_line,
                    s.signature,
                    s.language,
                )
                for s in symbols
            ],
        )

        self._conn.executemany(
            "INSERT INTO calls (symbol_name, caller_file, line, context, full_name) "
            "VALUES (?, ?, ?, ?, ?)",
            [(c.symbol_name, key, c.line, c.context, c.full_name) for c in calls],
        )

        self._conn.executemany(
            "INSERT INTO imports (symbol_name, file, import_line) VALUES (?, ?, ?)",
            [(i.symbol_name, key, i.import_line) for i in imports],
        )

        self._conn.execute(
            "INSERT OR REPLACE INTO file_meta (file, content_hash, last_indexed, language, line_count) "
            "VALUES (?, ?, ?, ?, ?)",
            (key, content_hash, time.time(), language, line_count),
        )

    def _replace_git_info_unlocked(
        self, filepath: Path, last_modified: str, commit_hash: str
    ) -> None:
        """Caller must hold an open transaction."""
        key = str(filepath)
        self._conn.execute(
            "INSERT OR REPLACE INTO git_info (file, last_modified, last_commit_hash) "
            "VALUES (?, ?, ?)",
            (key, last_modified, commit_hash),
        )

    def upsert_file(
        self,
        filepath: Path,
        content_hash: str,
        language: str,
        line_count: int,
        symbols,
        calls,
        imports,
    ):
        with self._conn:
            self._write_file_index_unlocked(
                filepath,
                content_hash,
                language,
                line_count,
                symbols,
                calls,
                imports,
            )

    def apply_index_batch(self, items: list[IndexBatchItem]) -> None:
        """Commit many files in one transaction (per-file delete+insert semantics preserved)."""
        with self._conn:
            for item in items:
                relative_path = Path(item.filepath)
                self._write_file_index_unlocked(
                    relative_path,
                    item.content_hash,
                    item.language,
                    item.line_count,
                    item.symbols,
                    item.calls,
                    item.imports,
                )
                if item.git_commit_hash:
                    self._replace_git_info_unlocked(
                        relative_path,
                        item.git_last_modified or "",
                        item.git_commit_hash,
                    )

    def _remove_file_unlocked(self, filepath: Path) -> None:
        key = str(filepath)
        self._conn.execute("DELETE FROM symbols WHERE file = ?", (key,))
        self._conn.execute("DELETE FROM calls WHERE caller_file = ?", (key,))
        self._conn.execute("DELETE FROM imports WHERE file = ?", (key,))
        self._conn.execute("DELETE FROM file_meta WHERE file = ?", (key,))
        self._conn.execute("DELETE FROM git_info WHERE file = ?", (key,))

    def remove_file(self, filepath: Path):
        with self._conn:
            self._remove_file_unlocked(filepath)

    def remove_files_batch(self, paths: list[Path]) -> None:
        """Remove index rows for many paths in one transaction."""
        with self._conn:
            for path in paths:
                self._remove_file_unlocked(path)

    def search_symbols(self, fts_query: str, limit: int = 15) -> List[Row]:
        return self.execute(
            """
            SELECT s.id, s.name, s.kind, s.file, s.start_line, s.end_line,
                   s.signature, s.language, bm25(symbols_fts) AS rank
            FROM symbols_fts
            JOIN symbols s ON s.id = symbols_fts.rowid
            WHERE symbols_fts MATCH ?
            ORDER BY rank
            LIMIT ?
            """,
            (fts_query, limit),
        )

    def search_calls(self, fts_query: str, limit: int = 15) -> List[Row]:
        return self.execute(
            """
            SELECT c.id, c.symbol_name, c.caller_file, c.line, c.context,
                   c.full_name, bm25(calls_fts) AS rank
            FROM calls_fts
            JOIN calls c ON c.id = calls_fts.rowid
            WHERE calls_fts MATCH ?
            ORDER BY rank
            LIMIT ?
            """,
            (fts_query, limit),
        )

    def get_symbol(self, name: str) -> List[Row]:
        return self.execute(
            "SELECT * FROM symbols WHERE name = ? ORDER BY file, start_line", (name,)
        )

    def get_symbol_ilike(self, name: str) -> List[Row]:
        return self.execute(
            "SELECT * FROM symbols WHERE name LIKE ? ORDER BY file, start_line",
            (f"%{name}%",),
        )

    def get_callers(self, symbol_name: str) -> List[Row]:
        return self.execute(
            "SELECT * FROM calls WHERE symbol_name = ? ORDER BY caller_file, line",
            (symbol_name,),
        )

    def get_importers(self, symbol_name: str) -> List[Row]:
        return self.execute(
            "SELECT * FROM imports WHERE symbol_name = ? ORDER BY file",
            (symbol_name,),
        )

    def get_git_info(self, filepath: Path) -> Optional[Row]:
        key = str(filepath)
        rows = self.execute("SELECT * FROM git_info WHERE file = ?", (key,))
        return rows[0] if rows else None

    def stats(self) -> dict:
        (file_count,) = self._conn.execute("SELECT COUNT(*) FROM file_meta").fetchone()
        (symbol_count,) = self._conn.execute("SELECT COUNT(*) FROM symbols").fetchone()
        lang_rows = self._conn.execute(
            """
            SELECT 
            language, 
            COUNT(*) as n 
            FROM file_meta 
            GROUP BY language 
            ORDER BY n DESC
            """
        ).fetchall()
        return {
            "files": file_count,
            "symbols": symbol_count,
            "languages": {r["language"]: r["n"] for r in lang_rows},
        }

    def module_summary(self) -> List[Row]:
        """Per-directory file and symbol counts for overview."""
        return self.execute(
            """
            SELECT
                COALESCE(
                    CASE WHEN instr(s.file, '/') > 0
                         THEN substr(s.file, 1, instr(s.file, '/') - 1)
                         ELSE '.'
                    END, '.'
                ) AS module,
                COUNT(DISTINCT s.file) AS file_count,
                COUNT(*) AS symbol_count
            FROM symbols s
            GROUP BY module
            ORDER BY file_count DESC
            """
        )

    def list_files(self) -> List[Path]:
        rows = self.execute("SELECT file FROM file_meta ORDER BY file")
        return [Path(row["file"]) for row in rows]
