"""OpenAI vision classifier for waste-report photos."""

import base64
import json
from typing import Any

import httpx

from app.schemas.classification import WASTE_CATEGORIES, ClassificationResult
from app.services.classifier.base import WasteClassifier

_RESPONSES_URL = "https://api.openai.com/v1/responses"
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


class OpenAIWasteClassifier(WasteClassifier):
    """Classify a report image with the OpenAI Responses API."""

    def __init__(self, api_key: str, model: str) -> None:
        if api_key == "change-me":
            raise ValueError("Set AI_API_KEY before using the OpenAI classifier.")
        self._api_key = api_key
        self._model = model

    async def classify(self, image_bytes: bytes) -> ClassificationResult:
        image_data = base64.b64encode(image_bytes).decode("ascii")
        payload = {
            "model": self._model,
            "input": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": f"{_PROMPT} Categories: {', '.join(WASTE_CATEGORIES)}.",
                        },
                        {
                            "type": "input_image",
                            "image_url": f"data:image/jpeg;base64,{image_data}",
                            "detail": "low",
                        },
                    ],
                }
            ],
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "waste_classification",
                    "strict": True,
                    "schema": _OUTPUT_SCHEMA,
                }
            },
        }
        headers = {"Authorization": f"Bearer {self._api_key}"}
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(_RESPONSES_URL, headers=headers, json=payload)
            response.raise_for_status()

        raw: dict[str, Any] = response.json()
        result = _parse_output(raw)
        return ClassificationResult(
            is_valid_report=result["is_valid_report"],
            category=result["category"],
            confidence=result["confidence"],
            raw={"provider": "openai", "model": self._model, "response_id": raw.get("id")},
        )


def _parse_output(response: dict[str, Any]) -> dict[str, Any]:
    """Extract the JSON-schema output text from a Responses API response."""
    for item in response.get("output", []):
        for content in item.get("content", []):
            if content.get("type") == "output_text":
                parsed = json.loads(content["text"])
                if isinstance(parsed, dict):
                    return parsed
    raise ValueError("OpenAI response did not contain a structured classification result.")
