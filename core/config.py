"""Application settings via pydantic-settings."""
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="CONCIERGE_",
        env_file=".env",
        extra="ignore",
    )

    env: str = "dev"
    debug: bool = True
    log_level: str = "INFO"

    project_root: Path = PROJECT_ROOT
    database_path: Path = PROJECT_ROOT / "concierge.db"
    lifecycle_root: Path = PROJECT_ROOT / "_legacy" / "tool-requests"
    memory_store_path: Path | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
