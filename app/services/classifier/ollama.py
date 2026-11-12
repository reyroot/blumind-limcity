"""Ollama vision classifier for locally hosted models."""

import base64
import json
from typing import Any

import httpx

from app.schemas.classification import WASTE_CATEGORIES, ClassificationResult
from app.services.classifier.base import WasteClassifier

_PROMPT = """First decide whether this is a valid public waste-disposal report. It is valid only
when the image visibly shows discarded garbage or waste in an outdoor/public area. Mark it invalid
for indoor scenes, clean streets, unrelated objects/people/animals, screenshots, images too unclear
to verify waste, or a correctly used garbage bin/container. Then classify valid waste. Select
exactly one category from the supplied taxonomy. Use `general` when waste is visible but no category
is dominant. Do not infer hazardous waste unless it is visibly identifiable.
Return a confidence from 0 to 1."""

_OUTPUT_SCHEMA: dict[str, object] = {
    "type": "object",
    "properties": {
        "is_valid_report": {"type": "boolean"},
        "category": {"type": "string", "enum": list(WASTE_CATEGORIES)},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
    },
    "required": ["is_valid_report", "category", "confidence"],
    "additionalProperties": False,
}


class OllamaWasteClassifier(WasteClassifier):
    """Classify a report image through an Ollama-compatible local REST endpoint."""

    def __init__(self, base_url: str, model: str, timeout_seconds: float = 180.0) -> None:
        self._chat_url = f"{base_url.rstrip('/')}/api/chat"
        self._model = model
        self._timeout_seconds = timeout_seconds

    async def classify(self, image_bytes: bytes) -> ClassificationResult:
        image_data = base64.b64encode(image_bytes).decode("ascii")
        payload = {
            "model": self._model,
            "stream": False,
            "messages": [
                {
                    "role": "user",
                    "content": f"{_PROMPT} Categories: {', '.join(WASTE_CATEGORIES)}.",
                    "images": [image_data],
                }
            ],
            "format": _OUTPUT_SCHEMA,
            "options": {"temperature": 0},
        }
        async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
            response = await client.post(self._chat_url, json=payload)
            response.raise_for_status()

        raw: dict[str, Any] = response.json()
        content = raw.get("message", {}).get("content")
        if not isinstance(content, str):
            raise ValueError("Ollama response did not contain a classification result.")
        result = json.loads(content)
        if not isinstance(result, dict):
            raise ValueError("Ollama classification result was not a JSON object.")
        return ClassificationResult(
            is_valid_report=result["is_valid_report"],
            category=result["category"],
            confidence=result["confidence"],
            raw={
                "provider": "ollama",
                "model": self._model,
                "total_duration_ns": raw.get("total_duration"),
            },
        )
