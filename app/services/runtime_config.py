"""Runtime setup edited from the admin panel.

Environment variables remain the defaults. After the first save, ``data/runtime_config.json``
wins for the operational fields so a presentation can switch classifiers without a restart.
The API key is stored in that file (mode 0600) and is never returned by the admin API.
"""

import json
import logging
from pathlib import Path

from pydantic import ValidationError

from app.core.settings import settings
from app.schemas.admin import AdminConfigPublic, AdminConfigUpdate, ProviderName

logger = logging.getLogger(__name__)


class RuntimeConfig(AdminConfigUpdate):
    """Full config including the secret key."""


def _provider_default() -> ProviderName:
    if settings.ai_provider == "yolo":
        return "gemini"
    return settings.ai_provider


def defaults_from_settings() -> RuntimeConfig:
    return RuntimeConfig(
        demo_mode=settings.demo_mode,
        ai_provider=_provider_default(),
        openai_model=settings.openai_model,
        ollama_base_url=settings.ollama_base_url.rstrip("/"),
        ollama_model=settings.ollama_model,
        ollama_timeout_seconds=settings.ollama_timeout_seconds,
        cursor_cli_bin=settings.cursor_cli_bin,
        cursor_model=settings.cursor_model,
        cursor_timeout_seconds=settings.cursor_timeout_seconds,
        ai_api_key=settings.ai_api_key,
    )


def config_path() -> Path:
    return Path(settings.runtime_config_path)


def load_runtime_config() -> RuntimeConfig:
    """Return saved overrides merged onto the current environment defaults."""
    base = defaults_from_settings()
    path = config_path()
    if not path.is_file():
        return base
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        logger.exception("Ignoring unreadable runtime config at %s", path)
        return base
    if not isinstance(raw, dict):
        return base
    merged = base.model_dump()
    for key in merged:
        if key in raw and raw[key] is not None:
            merged[key] = raw[key]
    try:
        return RuntimeConfig.model_validate(merged)
    except ValidationError:
        logger.exception("Ignoring invalid runtime config at %s", path)
        return base


def save_runtime_config(update: AdminConfigUpdate) -> RuntimeConfig:
    """Persist a full admin update. A blank API key keeps the current one."""
    current = load_runtime_config()
    payload = update.model_dump()
    if not payload.get("ai_api_key"):
        payload["ai_api_key"] = current.ai_api_key
    cfg = RuntimeConfig.model_validate(payload)
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(cfg.model_dump_json(indent=2), encoding="utf-8")
    try:
        path.chmod(0o600)
    except OSError:
        logger.warning("Could not restrict permissions on %s", path)
    return cfg


def public_config(cfg: RuntimeConfig | None = None) -> AdminConfigPublic:
    current = cfg or load_runtime_config()
    key = current.ai_api_key
    return AdminConfigPublic(
        demo_mode=current.demo_mode,
        ai_provider=current.ai_provider,
        openai_model=current.openai_model,
        ollama_base_url=current.ollama_base_url,
        ollama_model=current.ollama_model,
        ollama_timeout_seconds=current.ollama_timeout_seconds,
        cursor_cli_bin=current.cursor_cli_bin,
        cursor_model=current.cursor_model,
        cursor_timeout_seconds=current.cursor_timeout_seconds,
        ai_api_key_set=bool(key) and key != "change-me",
        image_storage_dir=settings.image_storage_dir,
    )
