"""Application-level exceptions.

Keeping domain errors here (instead of raising HTTPException in services) keeps the
service layer transport-agnostic. The API layer maps these to HTTP responses.
"""


class LimcityError(Exception):
    """Base class for all application errors."""


class InvalidSignatureError(LimcityError):
    """Raised when a webhook payload fails signature verification."""


class MediaDownloadError(LimcityError):
    """Raised when a WhatsApp media asset cannot be downloaded."""


class ClassificationError(LimcityError):
    """Raised when the AI classifier fails to process an image."""
