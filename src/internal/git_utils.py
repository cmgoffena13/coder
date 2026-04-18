import functools
import subprocess
from pathlib import Path

_GIT_TIMEOUT_S = 5


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


def get_last_commit(filepath: str, project_dir: Path) -> tuple[str, str]:
    """Return (commit_hash, author_date) for the last commit touching ``filepath``.

    ``filepath`` is a repo-relative path string (as stored in the index). ``project_dir``
    is the repository root used as ``git``'s working directory.
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
