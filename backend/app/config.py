"""
Application configuration, loaded from environment variables (see
.env.example at the repo root). Every other module reads config from here —
do not call `os.environ` directly elsewhere.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- App ---
    environment: str = "development"
    log_level: str = "INFO"
    backend_cors_origins: str = "http://localhost:5173"

    # --- Database ---
    database_url: str = "postgresql+psycopg2://recoverai:recoverai@localhost:5432/recoverai"

    # --- Redis / Celery ---
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/1"

    # --- Razorpay (test mode only) ---
    razorpay_key_id: str = ""
    razorpay_key_secret: str = ""
    razorpay_webhook_secret: str = ""

    # --- LLM fallback classifier ---
    llm_provider: str = "none"  # "none" | "anthropic" | "openai"
    llm_api_key: str = ""
    llm_model: str = ""

    # --- Recovery defaults (fallback when no StoppingRuleConfig row matches) ---
    default_max_retry_attempts: int = 3
    default_max_days_open: int = 7

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.backend_cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    """Cached settings accessor — import and call this, don't instantiate Settings() directly."""
    return Settings()
