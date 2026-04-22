"""Application settings via pydantic-settings."""
from functools import lru_cache
from pathlib import Path

from pydantic import SecretStr
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

    memory_dir: Path = Path.home() / ".concierge-memory"
    memory_embedding_model: str = "all-MiniLM-L6-v2"

    # Anthropic / recommendation engine (N6).
    # API key resolution falls back to the SDK-default env var
    # ANTHROPIC_API_KEY when CONCIERGE_ANTHROPIC_API_KEY is unset;
    # that fallback is handled in core.recommend.client, not here,
    # so this field only binds to the Concierge-prefixed variable.
    anthropic_api_key: SecretStr | None = None

    # Pinned exactly per DECISIONS [2026-04-22 07:26] — the 48h
    # operational shakedown requires that variance in recommendations
    # comes from real input differences, not model sampling or a
    # floating alias like "claude-opus-latest".
    anthropic_model: str = "claude-opus-4-7"

    # Default 0.0 per Phase E Q2 + operational-first pivot. Override
    # via CONCIERGE_RECOMMEND_TEMPERATURE=X produces a loud DEBUG log
    # at service init and per-request while active; any non-zero
    # value is development/fixture-tuning only.
    recommend_temperature: float = 0.0
    recommend_max_tokens: int = 2048
    recommend_memory_search_limit: int = 5


@lru_cache
def get_settings() -> Settings:
    return Settings()
