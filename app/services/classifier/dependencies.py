"""Dependency-injection provider for the active WasteClassifier strategy.

Selects the concrete implementation from settings. FastAPI routes/services depend on
``get_classifier`` (via ``Depends``), keeping them decoupled from the provider choice.
"""

from app.core.settings import settings
from app.services.classifier.base import WasteClassifier
from app.services.classifier.gemini import GeminiWasteClassifier


def get_classifier() -> WasteClassifier:
    match settings.ai_provider:
        case "gemini" | "openai":
            return GeminiWasteClassifier(api_key=settings.ai_api_key)
        case "yolo":
            # Placeholder for the future custom model strategy.
            raise NotImplementedError("YOLOv8 classifier not implemented yet.")
        case _:  # pragma: no cover - guarded by settings validation
            raise ValueError(f"Unknown AI provider: {settings.ai_provider}")
