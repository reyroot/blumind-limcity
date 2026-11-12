"""Dependency-injection provider for the active WasteClassifier strategy.

The admin panel writes a runtime config file. Each call reads that file so the next
report uses the provider selected in /admin without restarting the process.
"""

from app.services.classifier.base import WasteClassifier
from app.services.classifier.cursor_cli import CursorCliWasteClassifier
from app.services.classifier.gemini import GeminiWasteClassifier
from app.services.classifier.ollama import OllamaWasteClassifier
from app.services.classifier.openai import OpenAIWasteClassifier
from app.services.runtime_config import load_runtime_config


def get_classifier() -> WasteClassifier:
    cfg = load_runtime_config()
    match cfg.ai_provider:
        case "gemini":
            return GeminiWasteClassifier(api_key=cfg.ai_api_key or "")
        case "openai":
            return OpenAIWasteClassifier(api_key=cfg.ai_api_key or "", model=cfg.openai_model)
        case "ollama":
            return OllamaWasteClassifier(
                base_url=cfg.ollama_base_url,
                model=cfg.ollama_model,
                timeout_seconds=cfg.ollama_timeout_seconds,
            )
        case "cursor":
            return CursorCliWasteClassifier(
                cli_bin=cfg.cursor_cli_bin,
                model=cfg.cursor_model,
                timeout_seconds=cfg.cursor_timeout_seconds,
            )
        case _:  # pragma: no cover - guarded by the config schema
            raise ValueError(f"Unknown AI provider: {cfg.ai_provider}")
