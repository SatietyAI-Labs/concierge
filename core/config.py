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

    memory_dir: Path = Path.home() / ".concierge-memory"
    memory_embedding_model: str = "all-MiniLM-L6-v2"

    # Lifecycle-store root (N7). Isolated default — mirrors the
    # memory-isolation pattern per DECISIONS [2026-04-21 18:00]. The
    # `_legacy/tool-requests/` symlink points at Alfred's live
    # production folder; writing there mid-soak risks contaminating
    # Alfred's production cron with Concierge-under-development
    # output. Opt-in to the shared store via `CONCIERGE_LIFECYCLE_ROOT`.
    lifecycle_root: Path = Path.home() / ".concierge-lifecycle"

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

    # MCP protocolVersion advertised by the Claude Code adapter shim
    # (R1 closure — DECISIONS [2026-04-22 11:49] option iii chosen).
    # Default tracks current Claude Code 2.1.117, which sends
    # `2025-11-25` in its initialize request AND rejects server
    # responses with earlier versions ("Server's protocol version is
    # not supported"). Manual verification on 2026-04-22 surfaced
    # the rejection; the initial R1 default had a transcription
    # typo (`2025-11-05` — see DECISIONS correction note).
    # Override via CONCIERGE_CLAUDE_CODE_PROTOCOL_VERSION when a
    # future Claude Code version shifts the accepted-version set.
    #
    # The value is read once at shim process startup; mid-session
    # env changes do not take effect until the next shim restart
    # (matches the CONCIERGE_URL pattern in
    # adapters/claude_code/meta_tools/http_client.py).
    claude_code_protocol_version: str = "2025-11-25"


@lru_cache
def get_settings() -> Settings:
    return Settings()
