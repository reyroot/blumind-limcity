"""Stable contract for AI classification results.

This schema is the boundary between the classifier Strategy and the rest of the app.
Keeping it stable means swapping the third-party provider for a future YOLOv8 model
does not ripple through services or the database layer.
"""

from pydantic import BaseModel, Field


class ClassificationResult(BaseModel):
    category: str = Field(description="Predicted waste category, e.g. 'organic'.")
    confidence: float = Field(ge=0.0, le=1.0, description="Model confidence [0, 1].")
    raw: dict[str, object] = Field(
        default_factory=dict,
        description="Provider-specific raw payload for debugging/auditing.",
    )
