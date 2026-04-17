from functools import lru_cache
from pathlib import Path
from typing import Literal, Optional

from pydantic_settings import BaseSettings, SettingsConfigDict

LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


def _env_file_paths() -> tuple[str, ...]:
    paths: list[str] = []
    repo_root = Path(__file__).resolve().parent.parent
    # NOTE: Local for Development
    if (repo_root / "pyproject.toml").is_file():
        paths.append(str(repo_root / ".env"))
    # NOTE: Global for Production
    paths.append(str(Path.home() / ".config" / "coder" / ".env"))
    return tuple(paths)


class GlobalConfig(BaseSettings):
    CODER_LOG_LEVEL: LogLevel = "ERROR"
    CODER_OLLAMA_HOST: str = "http://localhost:11434"
    CODER_OLLAMA_MODEL: Optional[str] = None

    model_config = SettingsConfigDict(env_file=_env_file_paths(), extra="ignore")


@lru_cache()
def get_config():
    return GlobalConfig()


config = get_config()
