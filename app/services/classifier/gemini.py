"""Third-party vision API classifier (MVP placeholder).

This is a PLACEHOLDER: it returns a random plausible category so the end-to-end
pipeline and dashboard are demonstrable without external credentials. Replace
``classify`` with a real async call to the vision provider (Gemini/GPT) using
``self._api_key`` when ready — the return contract stays the same.
"""

import random

from app.schemas.classification import WASTE_CATEGORIES, ClassificationResult
from app.services.classifier.base import WasteClassifier


class GeminiWasteClassifier(WasteClassifier):
    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    async def classify(self, image_bytes: bytes) -> ClassificationResult:
        # TODO: call the real vision API here (async httpx call, timeout + retries).
        category = random.choice(WASTE_CATEGORIES)
        return ClassificationResult(
            category=category,
            confidence=round(random.uniform(0.6, 0.99), 2),
            raw={"provider": "gemini", "note": "placeholder implementation"},
        )
