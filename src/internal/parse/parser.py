import os
import time
from pathlib import Path
from typing import Optional, Union

import xxhash

from src.internal.git_utils import (
    ignored_path_names_from_gitignore,
    last_commits_for_paths,
    norm_git_repo_path,
)
from src.internal.parse.base import LanguageAdapter
from src.internal.parse.db import IndexBatchItem, IndexDB
from src.internal.parse.languages.factory import AdapterFactory
from src.internal.workspace import WorkspaceContext

INDEX_DB_BATCH_SIZE = 1000


class Parser:
    def __init__(self) -> None:
        self._adapters_by_ext: dict[str, Optional[LanguageAdapter]] = {}
        self._index_batch: list[IndexBatchItem] = []

    def _adapter_for(self, filename: str) -> Optional[LanguageAdapter]:
        """Return a language adapter for ``filename`` (cached by extension)."""
        ext = os.path.splitext(filename)[1].lower()
        if ext not in self._adapters_by_ext:
            self._adapters_by_ext[ext] = AdapterFactory.get_adapter(filename)
        return self._adapters_by_ext[ext]

    def _flush_index_batch(
        self, db: IndexDB, *, proj_root: Path, git_metadata: bool
    ) -> tuple[int, int]:
        """Persist :attr:`_index_batch` and clear it. Returns ``(files_count, symbol_count)``."""
        batch = self._index_batch
        if not batch:
            return (0, 0)
        num_files = len(batch)
        num_symbols = sum(len(item.symbols) for item in batch)
        if git_metadata:
            paths = list(
                dict.fromkeys(norm_git_repo_path(item.filepath) for item in batch)
            )
            commits = last_commits_for_paths(
                proj_root, paths, chunk_size=INDEX_DB_BATCH_SIZE
            )
            for item in batch:
                key = norm_git_repo_path(item.filepath)
                item.git_commit_hash, item.git_last_modified = commits.get(
                    key, ("", "")
                )
        db.apply_index_batch(batch)
        batch.clear()
        return (num_files, num_symbols)

    def parse_project(
        self,
        directory: Path,
        db: IndexDB,
        git_metadata: bool,
        full_refresh: bool = False,
    ) -> dict[str, Union[int, float]]:
        start = time.time()

        proj_root = directory.resolve()
        ignore_dirs = ignored_path_names_from_gitignore(proj_root)
        self._index_batch.clear()

        files_indexed = 0
        files_skipped = 0
        total_symbols = 0
        present_rel_paths: set[str] = set()

        for dirpath, dirnames, filenames in os.walk(proj_root):
            dirnames[:] = [
                d for d in dirnames if d not in ignore_dirs and not d.startswith(".")
            ]
            for file in filenames:
                abs_path = Path(dirpath) / file
                rel_path = str(abs_path.relative_to(proj_root))
                present_rel_paths.add(rel_path)

                adapter = self._adapter_for(file)

                if adapter is None:
                    files_skipped += 1
                    continue

                if abs_path.stat().st_size > 1_000_000:  # 1 MB — skip very large files
                    files_skipped += 1
                    continue

                try:
                    source = abs_path.read_bytes()
                except OSError:
                    files_skipped += 1
                    continue

                content_hash = xxhash.xxh128(source).hexdigest()

                if not full_refresh and not db.is_stale(rel_path, content_hash):
                    files_skipped += 1
                    continue

                try:
                    source_lines = source.decode("utf-8", errors="replace").splitlines()
                    tree = adapter.parse_file(source, rel_path)
                    symbols, calls, imports = adapter.extract_index_data(
                        tree, source_lines, rel_path
                    )
                except Exception:
                    files_skipped += 1
                    continue

                self._index_batch.append(
                    IndexBatchItem(
                        filepath=rel_path,
                        content_hash=content_hash,
                        language=adapter.language_name,
                        line_count=len(source_lines),
                        symbols=symbols,
                        calls=calls,
                        imports=imports,
                    )
                )
                if len(self._index_batch) >= INDEX_DB_BATCH_SIZE:
                    file_count, symbol_count = self._flush_index_batch(
                        db, proj_root=proj_root, git_metadata=git_metadata
                    )
                    files_indexed += file_count
                    total_symbols += symbol_count

        file_count, symbol_count = self._flush_index_batch(
            db, proj_root=proj_root, git_metadata=git_metadata
        )
        files_indexed += file_count
        total_symbols += symbol_count

        to_remove = [
            indexed_rel
            for indexed_rel in db.list_files()
            if indexed_rel not in present_rel_paths
        ]
        db.remove_files_batch(to_remove)

        elapsed = time.time() - start
        return {
            "files_indexed": files_indexed,
            "files_skipped": files_skipped,
            "symbols": total_symbols,
            "elapsed": elapsed,
        }


parser = Parser()


def index_workspace(
    workspace: WorkspaceContext, full_refresh: bool = False
) -> dict[str, Union[int, float]]:
    db = IndexDB(workspace.root)
    try:
        return parser.parse_project(
            workspace.root,
            db,
            full_refresh=full_refresh,
            git_metadata=workspace.is_git_repo,
        )
    finally:
        db.close()
