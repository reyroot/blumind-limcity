"""Application settings loaded from environment variables.

We use pydantic-settings so secrets (DB URI, API keys, WhatsApp tokens) are never
hardcoded and are validated at startup. Import the shared ``settings`` singleton.
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Application
    app_name: str = "Limcity"
    app_env: Literal["development", "staging", "production"] = "development"
    debug: bool = True

    # Database (PostgreSQL + PostGIS). Async driver required (psycopg 3).
    database_url: str = Field(
        default="postgresql+psycopg://limcity:limcity@localhost:5432/limcity",
    )

    # Meta WhatsApp Cloud API
    whatsapp_verify_token: str = "change-me"
    whatsapp_access_token: str = "change-me"
    whatsapp_app_secret: str = "change-me"
    # Sender id used to POST outbound replies (from the WhatsApp number's settings).
    whatsapp_phone_number_id: str = "change-me"
    whatsapp_graph_version: str = "v25.0"

    # AI / Vision classifier. Admin panel can override these at runtime.
    ai_provider: Literal["gemini", "openai", "ollama", "cursor", "yolo"] = "gemini"
    ai_api_key: str = "change-me"
    openai_model: str = "gpt-5"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "gemma3"
    ollama_timeout_seconds: float = 180.0

    # Presentation mode: save the photo immediately and let the worker classify it.
    demo_mode: bool = True
    cursor_cli_bin: str = "agent"
    cursor_model: str = ""
    cursor_timeout_seconds: float = 180.0
    image_storage_dir: str = "data/report-images"
    runtime_config_path: str = "data/runtime_config.json"

    # Telegram Bot API
    telegram_bot_token: str = "change-me"
    # Optional secret passed to setWebhook; when unset (dev placeholder) verification is skipped.
    telegram_webhook_secret: str = "change-me"

    @property
    def whatsapp_configured(self) -> bool:
        """True when a real WhatsApp access token is set (not the dev placeholder).

        Gates both media download and outbound replies. When False the pipeline runs
        in dev mode: media download is skipped and replies are logged instead of sent.
        """
        return self.whatsapp_access_token != "change-me"

    @property
    def telegram_configured(self) -> bool:
        """True when a real Telegram bot token is set (not the dev placeholder)."""
        return self.telegram_bot_token != "change-me"


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance (read env once per process)."""
    return Settings()


settings: Settings = get_settings()
