import sys
import tomllib
from pathlib import Path
from typing import Any

import orjson


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
