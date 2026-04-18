import functools
import re
import subprocess
from pathlib import Path
from typing import Sequence

_GIT_TIMEOUT_S = 5

_COMMIT_LINE = re.compile(r"^([0-9a-f]{40})\t(.*)$")


@functools.lru_cache()
def ignored_path_names_from_gitignore(repo_root: Path) -> set[str]:
    """
    Return a cached set of *entry names* to ignore, derived from `.gitignore`.

    Only simple basename-style patterns are included (e.g. `.venv`, `dist`);
    trailing directory wildcards are peeled off first (`/*`, `/**`), so `.venv/*`
    becomes `.venv`. Other globs and multi-segment paths are skipped.
    """
    always_ignore = {".git", ".gitignore"}
    gitignore_path = repo_root / ".gitignore"
    if not gitignore_path.is_file():
        return always_ignore

    ignored: set[str] = set(always_ignore)
    for raw in gitignore_path.read_text(
        encoding="utf-8", errors="replace"
    ).splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("!"):
            continue
        line = line.removesuffix("/")
        line = line.lstrip("/")
        while True:
            if line.endswith("/**"):
                line = line[:-3].removesuffix("/")
                continue
            if line.endswith("/*"):
                line = line[:-2].removesuffix("/")
                continue
            break
        if any(ch in line for ch in ("*", "?", "[", "]")):
            continue
        if "/" in line:
            continue
        ignored.add(line)
    return ignored


def is_git_work_tree(path: Path) -> bool:
    """True if ``path`` is inside a git work tree (``git rev-parse --git-dir`` succeeds)."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            cwd=path,
            capture_output=True,
            text=True,
            timeout=_GIT_TIMEOUT_S,
        )
        return result.returncode == 0 and bool(result.stdout.strip())
    except Exception:
        return False


def run_git(cwd: Path, args: list[str], *, fallback: str = "") -> str:
    """
    Run ``git`` with the given argument list (not including the ``git`` executable).

    On failure or empty stdout, returns ``fallback``.
    """
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=cwd,
            capture_output=True,
            text=True,
            check=True,
            timeout=_GIT_TIMEOUT_S,
        )
        return result.stdout.strip() or fallback
    except Exception:
        return fallback


def norm_git_repo_path(filepath: str) -> str:
    """POSIX-style repo-relative path for comparing with ``git`` output.

    ``git log --name-only`` always uses ``/``. Paths from the indexer are often
    ``str(path.relative_to(root))``, which uses native Windows separators. The index
    and SQLite still store paths as strings; this only aligns those strings with
    what Git prints.
    """
    return Path(filepath).as_posix()


def _run_git_log_name_only_paths(project_dir: Path, paths: list[str]) -> str:
    try:
        result = subprocess.run(
            [
                "git",
                "log",
                "--no-renames",
                "--format=%H\t%ai",
                "--name-only",
                "--",
                *paths,
            ],
            cwd=project_dir,
            capture_output=True,
            text=True,
            timeout=_GIT_TIMEOUT_S,
        )
        if result.returncode != 0:
            return ""
        return result.stdout or ""
    except Exception:
        return ""


def _parse_git_log_last_touch(
    stdout: str, want: set[str]
) -> dict[str, tuple[str, str]]:
    """``want`` is normalized repo-relative paths; log is newest-first."""
    result: dict[str, tuple[str, str]] = {}
    cur: tuple[str, str] | None = None
    for raw in stdout.splitlines():
        line = raw.rstrip("\r\n")
        if not line.strip():
            continue
        m = _COMMIT_LINE.match(line)
        if m:
            cur = (m.group(1), m.group(2))
            continue
        if cur is None:
            continue
        fn = norm_git_repo_path(line.strip())
        if fn in want and fn not in result:
            result[fn] = cur
    return result


def last_commits_for_paths(
    project_dir: Path,
    paths: Sequence[str],
    *,
    chunk_size: int,
) -> dict[str, tuple[str, str]]:
    """
    Map repo-relative path (forward slashes) -> ``(commit_hash, author_date)`` for the
    latest commit touching that path. Paths with no history are omitted.

    Runs one ``git log`` per chunk of at most ``chunk_size`` pathspecs.
    """
    if not paths:
        return {}
    normalized = list(dict.fromkeys(norm_git_repo_path(p) for p in paths))
    out: dict[str, tuple[str, str]] = {}
    for start in range(0, len(normalized), chunk_size):
        chunk = normalized[start : start + chunk_size]
        want = set(chunk)
        if not want:
            continue
        log_out = _run_git_log_name_only_paths(project_dir, chunk)
        out.update(_parse_git_log_last_touch(log_out, want))
    return out


def get_last_commit(filepath: str, project_dir: Path) -> tuple[str, str]:
    """Return (commit_hash, author_date) for the last commit touching ``filepath``.

    ``filepath`` is a repo-relative path string (as stored in the index). ``project_dir``
    is the repository root used as ``git``'s working directory.

    For many paths, prefer :func:`last_commits_for_paths` (one ``git log`` per chunk).
    """
    out = run_git(
        project_dir,
        ["log", "-1", "--format=%H %ai", "--", filepath],
        fallback="",
    )
    if not out:
        return "", ""
    parts = out.split(" ", 1)
    return parts[0], parts[1] if len(parts) > 1 else ""
