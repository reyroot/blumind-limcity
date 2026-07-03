"""Third-party vision API classifier (MVP implementation).

This is a stub that returns a deterministic placeholder result so the pipeline is
end-to-end runnable without external credentials. Replace ``classify`` with a real
call to the vision provider (Gemini/GPT) using ``self._api_key``.
"""

from app.schemas.classification import ClassificationResult
from app.services.classifier.base import WasteClassifier


class GeminiWasteClassifier(WasteClassifier):
    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    async def classify(self, image_bytes: bytes) -> ClassificationResult:
        # TODO: call the real vision API here (async httpx call, timeout + retries).
        return ClassificationResult(
            category="unclassified",
            confidence=0.0,
            raw={"provider": "gemini", "note": "stub implementation"},
        )
