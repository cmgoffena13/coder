from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict

from src.utils import ensure_dir, get_coder_config_dir


def _env_file_paths() -> tuple[str, ...]:
    paths: list[str] = []
    repo_root = Path(__file__).resolve().parent.parent
    # NOTE: Local for Development
    if (repo_root / "pyproject.toml").is_file():
        paths.append(str(repo_root / ".env"))
    # NOTE: Global for Production
    paths.append(str(Path.home() / ".config" / "coder" / ".env"))
    return tuple(paths)


@lru_cache()
def get_index_storage_dir() -> Path:
    repo_root = Path(__file__).resolve().parent.parent
    if (repo_root / "pyproject.toml").is_file():
        # NOTE: Local for Development
        return ensure_dir(repo_root / ".parse_index")
    # NOTE: Global for Production
    return get_coder_config_dir("parse_index")


def delete_all_parse_indexes() -> int:
    d = get_index_storage_dir()
    if not d.is_dir():
        return 0
    n = 0
    for p in sorted(d.glob("*.sqlite")):
        for path in (p, Path(f"{p}-wal"), Path(f"{p}-shm")):
            path.unlink(missing_ok=True)
        n += 1
    return n


class GlobalConfig(BaseSettings):
    CODER_OLLAMA_HOST: str = "http://localhost:11434"
    CODER_OLLAMA_MODEL: Optional[str] = None

    model_config = SettingsConfigDict(env_file=_env_file_paths(), extra="ignore")


@lru_cache()
def get_config():
    return GlobalConfig()


config = get_config()
