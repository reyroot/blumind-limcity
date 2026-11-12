"""Admin panel payloads. The API key is write-only."""

import re
from typing import Literal

from pydantic import BaseModel, Field, field_validator

ProviderName = Literal["gemini", "openai", "ollama", "cursor"]

_BIN_RE = re.compile(r"^[A-Za-z0-9_./\\:-]+$")
_MODEL_RE = re.compile(r"^[A-Za-z0-9_.:\[\]=,+-]*$")


class AdminConfigUpdate(BaseModel):
    demo_mode: bool
    ai_provider: ProviderName
    openai_model: str = Field(min_length=1, max_length=80)
    ollama_base_url: str = Field(min_length=1, max_length=200)
    ollama_model: str = Field(min_length=1, max_length=80)
    ollama_timeout_seconds: float = Field(gt=0, le=600)
    cursor_cli_bin: str = Field(min_length=1, max_length=200)
    cursor_model: str = Field(default="", max_length=120)
    cursor_timeout_seconds: float = Field(gt=0, le=600)
    ai_api_key: str | None = Field(default=None, max_length=400)

    @field_validator("ollama_base_url")
    @classmethod
    def _http_url(cls, value: str) -> str:
        if not value.startswith(("http://", "https://")):
            raise ValueError("Ollama URL must start with http:// or https://")
        return value.rstrip("/")

    @field_validator("cursor_cli_bin")
    @classmethod
    def _cli_bin(cls, value: str) -> str:
        if not _BIN_RE.fullmatch(value):
            raise ValueError("Cursor CLI command contains unsupported characters")
        return value

    @field_validator("openai_model", "ollama_model", "cursor_model")
    @classmethod
    def _model_name(cls, value: str) -> str:
        if not _MODEL_RE.fullmatch(value):
            raise ValueError("Model name contains unsupported characters")
        return value


class AdminConfigPublic(BaseModel):
    demo_mode: bool
    ai_provider: ProviderName
    openai_model: str
    ollama_base_url: str
    ollama_model: str
    ollama_timeout_seconds: float
    cursor_cli_bin: str
    cursor_model: str
    cursor_timeout_seconds: float
    ai_api_key_set: bool
    image_storage_dir: str


class AdminStatus(BaseModel):
    database_ok: bool
    by_status: dict[str, int]
    demo_mode: bool
    ai_provider: str


class DemoDataResult(BaseModel):
    inserted: int
    removed: int
