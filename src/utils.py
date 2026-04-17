import functools
import sys
import tomllib
from pathlib import Path
from typing import Any

import orjson


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


def get_version() -> str:
    """Get the version of the application."""
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        if not isinstance(meipass, str):
            raise RuntimeError("frozen build missing sys._MEIPASS")
        pyproject_path = Path(meipass) / "pyproject.toml"
        if not pyproject_path.exists():
            exe = Path(getattr(sys, "executable", None) or sys.argv[0])
            pyproject_path = exe.parent / "pyproject.toml"
    else:
        pyproject_path = Path(__file__).parent.parent / "pyproject.toml"

    if not pyproject_path.exists():
        raise FileNotFoundError(f"Could not find pyproject.toml at {pyproject_path}")

    with open(pyproject_path, "rb") as f:
        return tomllib.load(f)["project"]["version"]


def ensure_dir(path: Path) -> Path:
    """Create a directory if it doesn't exist."""
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_coder_config_dir(*parts: str) -> Path:
    """
    Base directory for Selene local config/data: ~/.config/coder

    If `parts` are provided, returns ~/.config/coder/<parts...> and creates it.
    """
    base = Path.home() / ".config" / "coder"
    return ensure_dir(base.joinpath(*parts))


def read_json(path: Path) -> Any:
    """Read a JSON file."""
    with path.open("rb") as f:
        return orjson.loads(f.read())


def write_json(path: Path, obj: Any) -> None:
    """Write a JSON file."""
    with path.open("wb") as f:
        f.write(orjson.dumps(obj))
