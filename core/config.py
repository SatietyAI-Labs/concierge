"""Application settings via pydantic-settings."""
from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr, field_validator
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

    # Multi-store read configuration (Stage 1A item 2; Gate 4.5 wires
    # this to four live store paths per [2026-05-13] D14 / D-V1.1
    # §III.3 Gate 4.5). Writes (memory.store, memory.identity_set)
    # always scope to `memory_dir`; only `memory.search` / `memory.list`
    # / `memory.stats` aggregate across these additional paths.
    #
    # Env var format: JSON list. Example (Gate 4.5):
    #   CONCIERGE_MEMORY_READ_STORES='["~/.moltbot-memory-v2", "~/.agent-memory/content-prep", "~/.agent-memory/intelligence", "~/.agent-memory/engagement"]'
    #
    # The validator expands `~` on each entry so operators can use the
    # tilde form in env-file edits without pre-expansion.
    memory_read_stores: list[Path] = Field(default_factory=list)

    @field_validator("memory_read_stores", mode="after")
    @classmethod
    def _expand_read_store_paths(cls, v: list[Path]) -> list[Path]:
        return [p.expanduser() for p in v]

    # Cold-start pre-warm (§VIII.2 / D88). When true, the service
    # schedules a background `MemoryClient.prewarm()` at startup so the
    # ChromaDB + sentence-transformers warmup tax (34–55s) is paid in a
    # controlled moment rather than on an agent's first /recommend
    # call. The test suite sets `CONCIERGE_PREWARM_ON_STARTUP=false`
    # (tests/conftest.py) so app-construction tests don't load the
    # embedding model; production inherits the default-on.
    prewarm_on_startup: bool = True

    # Root dir under which the three Claude skills-layout subdirs
    # (`public`, `user`, `examples`) live. Default is the Anthropic-
    # hosted path (Claude.ai / sandboxed-managed harness) — local
    # Claude Code CLI installs can override via `CONCIERGE_SKILLS_ROOT`
    # to point at e.g. `/home/you/.codex/skills/.system/` or a tmp
    # fixture dir. A missing root (or missing subdirs) is not an
    # error: the skills ingest path logs WARN and returns zero-ingested,
    # so first-boot on a fresh clone doesn't crash when /mnt/skills/
    # isn't present.
    skills_root: Path = Path("/mnt/skills")

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

    # Opus 4.7 deprecates the `temperature` parameter (manual
    # verification 2026-04-22 surfaced the 400 error:
    # "`temperature` is deprecated for this model"). The replacement
    # tuning knob per Anthropic's migration guide is
    # `output_config.effort`, which controls reasoning depth. Valid
    # values: "low" / "medium" / "high" / "xhigh" / "max".
    # Default "xhigh" matches the project's stated optimization
    # priority ("quality > token cost; effort stays at xhigh or max"
    # per CLAUDE.md). Override via CONCIERGE_RECOMMEND_EFFORT when
    # an operator wants to trade reasoning depth for token cost in
    # a specific deployment.
    # See DECISIONS [2026-04-22 15:45] for the temperature
    # deprecation fix rationale.
    claude_code_recommend_effort: str = "xhigh"
    # Bumped from 2048 → 4096 for the Opus 4.7 tokenizer's ~35%
    # token-count inflation (per Anthropic's migration guide). Round
    # number preserves the original N6 disposition ("raise to 4096
    # if soak shows truncations") — pre-firing rather than inventing
    # a new budget.
    recommend_max_tokens: int = 4096
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
