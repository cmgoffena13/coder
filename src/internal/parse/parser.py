import os
import subprocess
import time
from pathlib import Path
from typing import Union

import xxhash

from src.internal.parse.db import IndexDB
from src.internal.parse.languages.factory import AdapterFactory
from src.internal.workspace import WorkspaceContext
from src.utils import ignored_path_names_from_gitignore


def _content_hash(data: bytes) -> str:
    return xxhash.xxh128(data).hexdigest()


def _run(cmd: list[str], cwd: str) -> str:
    try:
        result = subprocess.run(
            cmd, cwd=cwd, capture_output=True, text=True, timeout=10
        )
        return result.stdout.strip()
    except Exception:
        return ""


def get_last_commit(filepath: str, project_dir: str) -> tuple[str, str]:
    """Return (commit_hash, author_date) for the last commit touching filepath."""
    out = _run(
        ["git", "log", "-1", "--format=%H %ai", "--", filepath],
        cwd=project_dir,
    )
    if not out:
        return "", ""
    parts = out.split(" ", 1)
    return parts[0], parts[1] if len(parts) > 1 else ""


def parse_project(
    directory: Path,
    db: IndexDB,
    full_refresh: bool = False,
    git_metadata: bool = True,
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

            adapter = AdapterFactory.get_adapter(file)

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

            content_hash = _content_hash(source)

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
                commit_hash, last_modified = get_last_commit(rel_path, str(proj_root))
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


def index_workspace(
    workspace: WorkspaceContext, full_refresh: bool = False
) -> dict[str, Union[int, float]]:
    db = IndexDB(workspace.root)
    try:
        return parse_project(
            workspace.root,
            db,
            full_refresh=full_refresh,
            git_metadata=workspace.is_git_repo,
        )
    finally:
        db.close()
