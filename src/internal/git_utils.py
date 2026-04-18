import functools
import re
import subprocess
from pathlib import Path
from typing import Sequence

_GIT_TIMEOUT_S = 5

_COMMIT_LINE = re.compile(r"^([0-9a-f]{40})\t(.*)$")


def _convert_path_for_git(relative_path: Path) -> str:
    """Repo-relative path string for ``git`` argv (forward slashes)."""
    return relative_path.as_posix()


def _token_from_git_log_path(line: str) -> str:
    """Normalize a ``git log --name-only`` line to the same string as :func:`_convert_path_for_git`."""
    return Path(line.strip()).as_posix()


@functools.lru_cache()
def ignored_path_names_from_gitignore(root: Path) -> set[str]:
    """
    Return a cached set of *entry names* to ignore, derived from `.gitignore`.

    Only simple basename-style patterns are included (e.g. `.venv`, `dist`);
    trailing directory wildcards are peeled off first (`/*`, `/**`), so `.venv/*`
    becomes `.venv`. Other globs and multi-segment paths are skipped.
    """
    always_ignore = {".git", ".gitignore"}
    gitignore_path = root / ".gitignore"
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


def _run_git_log_paths(root: Path, paths: list[str]) -> str:
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
            cwd=root,
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
    git_log_stdout: str, wanted_paths: set[str]
) -> dict[str, tuple[str, str]]:
    """First path line under a commit wins (log is newest-first).

    Keys are slash-normalized repo-relative paths matching ``wanted_paths``.
    Values are ``(commit_sha, author_date)`` for that commit.
    """
    newest_touch_by_path: dict[str, tuple[str, str]] = {}
    active_commit: tuple[str, str] | None = None
    for log_raw_line in git_log_stdout.splitlines():
        log_line = log_raw_line.rstrip("\r\n")
        if not log_line.strip():
            continue
        commit_header_match = _COMMIT_LINE.match(log_line)
        if commit_header_match:
            active_commit = (
                commit_header_match.group(1),
                commit_header_match.group(2),
            )
            continue
        if active_commit is None:
            continue
        relative_path = _token_from_git_log_path(log_line)
        if relative_path in wanted_paths and relative_path not in newest_touch_by_path:
            newest_touch_by_path[relative_path] = active_commit
    return newest_touch_by_path


def last_commits_for_paths(
    root: Path,
    paths: Sequence[Path],
    *,
    chunk_size: int,
) -> dict[Path, tuple[str, str]]:
    """
    Map repo-relative ``Path`` -> ``(commit_hash, author_date)`` for the latest commit
    touching that path. Paths with no history are omitted.

    Runs one ``git log`` per chunk of at most ``chunk_size`` paths.
    """
    if not paths:
        return {}
    unique = list(dict.fromkeys(paths))
    out: dict[Path, tuple[str, str]] = {}
    for start in range(0, len(unique), chunk_size):
        chunk_paths = unique[start : start + chunk_size]
        relative_paths = [_convert_path_for_git(p) for p in chunk_paths]
        if not relative_paths:
            continue
        log_output = _run_git_log_paths(root, relative_paths)
        newest_touch_by_path = _parse_git_log_last_touch(
            log_output, set(relative_paths)
        )
        for file_path, relative_path_str in zip(chunk_paths, relative_paths):
            if relative_path_str in newest_touch_by_path:
                out[file_path] = newest_touch_by_path[relative_path_str]
    return out


def get_last_commit(relative_path: Path, root: Path) -> tuple[str, str]:
    """Return (commit_hash, author_date) for the last commit touching ``relative_path``.

    ``relative_path`` is repo-relative. ``root`` is the repository root for ``git``.

    For many paths, prefer :func:`last_commits_for_paths` (one ``git log`` per chunk).
    """
    relative_path_str = _convert_path_for_git(relative_path)
    out = run_git(
        root,
        ["log", "-1", "--format=%H %ai", "--", relative_path_str],
        fallback="",
    )
    if not out:
        return "", ""
    parts = out.split(" ", 1)
    return parts[0], parts[1] if len(parts) > 1 else ""
