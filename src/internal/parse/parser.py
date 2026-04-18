import os
import time
from pathlib import Path
from typing import Optional, Union

import xxhash

from src.internal.git_utils import get_last_commit, ignored_path_names_from_gitignore
from src.internal.parse.base import LanguageAdapter
from src.internal.parse.db import IndexDB
from src.internal.parse.languages.factory import AdapterFactory
from src.internal.workspace import WorkspaceContext


class Parser:
    def __init__(self) -> None:
        self._adapters_by_ext: dict[str, Optional[LanguageAdapter]] = {}

    def _adapter_for(self, filename: str) -> Optional[LanguageAdapter]:
        """Return a language adapter for ``filename`` (cached by extension)."""
        ext = os.path.splitext(filename)[1].lower()
        if ext not in self._adapters_by_ext:
            self._adapters_by_ext[ext] = AdapterFactory.get_adapter(filename)
        return self._adapters_by_ext[ext]

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

        files_indexed = 0
        files_skipped = 0
        total_symbols = 0

        for dirpath, dirnames, filenames in os.walk(proj_root):
            dirnames[:] = [
                d for d in dirnames if d not in ignore_dirs and not d.startswith(".")
            ]
            for file in filenames:
                abs_path = Path(dirpath) / file
                rel_path = str(abs_path.relative_to(proj_root))

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

                    symbols = adapter.extract_symbols(tree, source_lines, rel_path)
                    calls = adapter.extract_calls(tree, source_lines, rel_path)
                    imports = adapter.extract_imports(tree, source_lines, rel_path)
                except Exception:
                    files_skipped += 1
                    continue

                db.upsert_file(
                    filepath=rel_path,
                    content_hash=content_hash,
                    language=adapter.language_name,
                    line_count=len(source_lines),
                    symbols=symbols,
                    calls=calls,
                    imports=imports,
                )
                if git_metadata:
                    commit_hash, last_modified = get_last_commit(rel_path, proj_root)
                    if commit_hash:
                        db.upsert_git_info(rel_path, last_modified, commit_hash)

                files_indexed += 1
                total_symbols += len(symbols)

        for indexed_file in db.list_files():
            if not (proj_root / indexed_file).exists():
                db.remove_file(indexed_file)

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
