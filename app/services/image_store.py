"""Local disk store for waste-report photos.

Files live outside the static dashboard directory so they are not directory-listed.
The public URL is always ``/api/reports/{id}/image``.
"""

from pathlib import Path

from app.core.settings import settings

_SUFFIXES: tuple[str, ...] = (".jpg", ".png", ".webp", ".gif")
_MEDIA_TYPES = {
    ".jpg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".gif": "image/gif",
}


def sniff_suffix(data: bytes) -> str:
    """Pick a file extension from image magic bytes. Unknown bytes are stored as JPEG."""
    if data.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if len(data) >= 12 and data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return ".webp"
    if data.startswith((b"GIF87a", b"GIF89a")):
        return ".gif"
    return ".jpg"


def media_type_for(path: Path) -> str:
    return _MEDIA_TYPES.get(path.suffix.lower(), "application/octet-stream")


class ImageStore:
    """Write and read one image file per report id."""

    def __init__(self, root: Path) -> None:
        self.root = root

    def save(self, report_id: int, data: bytes) -> str:
        """Persist ``data`` and return the public image URL."""
        if report_id < 1:
            raise ValueError("report_id must be positive")
        if not data:
            raise ValueError("image is empty")
        self.root.mkdir(parents=True, exist_ok=True)
        suffix = sniff_suffix(data)
        for other in _SUFFIXES:
            if other != suffix:
                (self.root / f"{report_id}{other}").unlink(missing_ok=True)
        (self.root / f"{report_id}{suffix}").write_bytes(data)
        return f"/api/reports/{report_id}/image"

    def path_for(self, report_id: int) -> Path | None:
        if report_id < 1:
            return None
        for suffix in _SUFFIXES:
            path = self.root / f"{report_id}{suffix}"
            if path.is_file():
                return path
        return None

    def read(self, report_id: int) -> bytes | None:
        path = self.path_for(report_id)
        if path is None:
            return None
        return path.read_bytes()

    def delete(self, report_id: int) -> None:
        """Remove every stored file for this report."""
        if report_id < 1:
            return
        for suffix in _SUFFIXES:
            (self.root / f"{report_id}{suffix}").unlink(missing_ok=True)


def get_image_store() -> ImageStore:
    return ImageStore(Path(settings.image_storage_dir))


def store_report_image(report_id: int, image_bytes: bytes) -> str | None:
    """Save a non-empty photo. Empty bytes (dev media bypass) are skipped."""
    if not image_bytes:
        return None
    return get_image_store().save(report_id, image_bytes)
