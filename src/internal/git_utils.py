import functools
import re
import subprocess
from pathlib import Path
from typing import Optional, Sequence

_GIT_TIMEOUT_S = 5

_COMMIT_LINE = re.compile(r"^([0-9a-f]{40})\t(.*)$")


def _convert_path_for_git(relative_path: Path) -> str:
    """Repo-relative path string for ``git`` argv (forward slashes)."""
    return relative_path.as_posix()


def _path_from_git_log_line(line: str) -> Path:
    """One repo-relative path from a ``git log --name-only`` line (stripped)."""
    return Path(line.strip())


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


def run_git(cwd: Path, args: list[str], fallback: str = "") -> str:
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


def is_git_work_tree(path: Path) -> bool:
    """True if ``path`` is inside a git work tree (``git rev-parse --git-dir`` succeeds)."""
    return bool(run_git(path, ["rev-parse", "--git-dir"]))


def _run_git_log_paths(root: Path, relative_paths: list[Path]) -> str:
    path_strings = [_convert_path_for_git(p) for p in relative_paths]
    return run_git(
        root,
        [
            "log",
            "--no-renames",
            "--format=%H\t%ai",
            "--name-only",
            "--",
            *path_strings,
        ],
        fallback="",
    )


def _parse_git_log_last_touch(git_log_stdout: str) -> dict[Path, tuple[str, str]]:
    """First path line under a commit wins (log is newest-first).

    Callers must run ``git log`` with ``--`` path arguments so ``--name-only`` lines
    are already scoped to those paths (no extra membership filter needed).

    Keys are repo-relative :class:`~pathlib.Path` instances (compare to paths from
    ``Path.relative_to(repo_root)``).
    Values are ``(commit_sha, author_date)`` for that commit.
    """
    path_to_commit: dict[Path, tuple[str, str]] = {}
    active_commit: Optional[tuple[str, str]] = None
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
        repo_path = _path_from_git_log_line(log_line)
        if repo_path not in path_to_commit:
            path_to_commit[repo_path] = active_commit
    return path_to_commit


def last_commits_for_paths(
    root: Path, paths: Sequence[Path], chunk_size: int
) -> dict[Path, tuple[str, str]]:
    """
    Map repo-relative ``Path`` -> ``(commit_hash, author_date)`` for the latest commit
    touching that path. Paths with no history are omitted.

    Runs one ``git log`` per chunk of at most ``chunk_size`` paths.
    """
    unique = list(dict.fromkeys(paths))
    output: dict[Path, tuple[str, str]] = {}
    for start in range(0, len(unique), chunk_size):
        chunk_paths = unique[start : start + chunk_size]
        if not chunk_paths:
            continue
        log_output = _run_git_log_paths(root, chunk_paths)
        path_to_commit = _parse_git_log_last_touch(log_output)
        for file_path in chunk_paths:
            if file_path in path_to_commit:
                output[file_path] = path_to_commit[file_path]
    return output
