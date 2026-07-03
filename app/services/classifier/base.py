"""WasteClassifier Strategy interface.

Every classifier (third-party vision API today, custom YOLOv8 later) implements this
ABC and returns the stable ``ClassificationResult``. The API layer depends on this
abstraction, not a concrete provider, so implementations are swappable via DI.
"""

from abc import ABC, abstractmethod

from app.schemas.classification import ClassificationResult


class WasteClassifier(ABC):
    """Abstract strategy for classifying waste from an image."""

    @abstractmethod
    async def classify(self, image_bytes: bytes) -> ClassificationResult:
        """Classify raw image bytes into a waste category with a confidence score."""
        raise NotImplementedError
