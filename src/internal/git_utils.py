import functools
import re
import subprocess
from pathlib import Path

_GIT_TIMEOUT_S = 5

_COMMIT_LINE = re.compile(r"^([0-9a-f]{40})\t(.*)$")


def _convert_path_for_git_command(relative_path: Path) -> str:
    return relative_path.as_posix()


def _convert_git_log_line_to_path(line: str) -> Path:
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
    return bool(run_git(path, ["rev-parse", "--git-dir"]))


def _run_git_log_paths(root: Path, relative_paths: list[Path]) -> str:
    path_strings = [_convert_path_for_git_command(path) for path in relative_paths]
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
    path_to_last_commit: dict[Path, tuple[str, str]] = {}
    last_commit: tuple[str, str] | None = None
    for log_raw_line in git_log_stdout.splitlines():
        log_line = log_raw_line.rstrip("\r\n")
        if not log_line.strip():
            continue
        commit_header_match = _COMMIT_LINE.match(log_line)
        if commit_header_match:
            last_commit = (
                commit_header_match.group(1),
                commit_header_match.group(2),
            )
            continue
        if last_commit is None:
            continue
        path = _convert_git_log_line_to_path(log_line)
        if path not in path_to_last_commit:
            path_to_last_commit[path] = last_commit
    return path_to_last_commit


def last_commits_for_paths(
    root: Path, paths: list[Path], chunk_size: int
) -> dict[Path, tuple[str, str]]:
    output: dict[Path, tuple[str, str]] = {}
    for start in range(0, len(paths), chunk_size):
        chunk_paths = paths[start : start + chunk_size]
        if not chunk_paths:
            continue
        log_output = _run_git_log_paths(root, chunk_paths)
        path_to_commit = _parse_git_log_last_touch(log_output)
        for file_path in chunk_paths:
            if file_path in path_to_commit:
                output[file_path] = path_to_commit[file_path]
    return output
