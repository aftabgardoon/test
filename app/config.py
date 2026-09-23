"""Application configuration loaded from environment variables / ``.env`` file."""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central configuration object.

    All values can be overridden through environment variables or a ``.env``
    file located in the working directory. See ``.env.example`` for the full
    list of supported variables.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- General ---
    app_name: str = "Multi-Channel Sync Bot"
    debug: bool = False
    environment: str = "development"

    # --- Database ---
    database_url: str = "sqlite+aiosqlite:///./syncbot.db"

    # --- Queue ---
    redis_url: str = "redis://redis:6379/0"
    queue_enabled: bool = False

    # --- Security ---
    fernet_key: str = ""
    webhook_secret: str = "change-me-to-a-long-random-string"

    # --- Bot Manager ---
    manager_bot_token: str = ""
    manager_bot_platform: str = "bale"
    # Secret that unlocks the manager bot UI.  Users must send
    # "/RSAsecret <value>" (or just "/RSAsecret" when the value equals the
    # default "RSAsecret") before they see any menu or reply.  Set to an empty
    # string to disable the gate (everyone allowed).
    manager_access_secret: str = "RSAsecret"
    # Public /start landing: the anonymous-message ("درگوشی") bot intro shown
    # to everyone who sends /start.  Empty disables the public landing.
    anonymous_bot_url: str = "https://ble.ir/daregooshi_bot"

    # --- Source listener bots (used by the pollers) ---
    bale_bot_token: str = ""
    rubika_bot_token: str = ""
    eitaa_bot_token: str = ""

    # --- Rate limiting / retry ---
    rate_limit_rps: int = 30
    retry_attempts: int = 3
    retry_backoff_base: float = 1.5

    # --- Polling (long polling) ---
    polling_enabled: bool = True
    polling_timeout: int = 15
    polling_retry_delay: float = 5.0
    polling_interval: float = 2.0

    # --- Concurrency (per-user/per-message tasks) ---
    worker_concurrency: int = 20


@lru_cache
def get_settings() -> Settings:
    """Return a cached :class:`Settings` instance."""
    return Settings()
