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

    # AI / Vision classifier
    ai_provider: Literal["gemini", "openai", "yolo"] = "gemini"
    ai_api_key: str = "change-me"

    @property
    def whatsapp_configured(self) -> bool:
        """True when a real WhatsApp access token is set (not the dev placeholder)."""
        return self.whatsapp_access_token != "change-me"


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance (read env once per process)."""
    return Settings()


settings: Settings = get_settings()
