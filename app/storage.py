"""Private photo storage primitives; callers must offload blocking methods.

Only canonical, decoded images enter storage. No static directory is exposed.
Filesystem/database coordination belongs to the report service, not this module.
"""
import io
import os
import re
import stat
import threading
import warnings
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from PIL import Image, ImageOps, UnidentifiedImageError

from app.errors import DomainError

# One decoder per process bounds peak pixel buffers and serializes this module's
# warning contexts (Python 3.12 warning filters are process-global).
DECODE_LOCK = threading.Lock()
MAX_PIXELS = 16_000_000
FORMATS = {"JPEG": ("jpg", "image/jpeg"), "PNG": ("png", "image/png"), "WEBP": ("webp", "image/webp")}
KEY = re.compile(r"[0-9a-f]{32}\.(jpg|png|webp)\Z")


def invalid_photo():
    return DomainError("invalid_photo", "Photo must be a valid, non-animated JPEG, PNG or WebP within the configured limits", 422)


async def read_upload(upload, max_bytes: int) -> bytes:
    """Bound reads including a one-byte overflow probe; caller owns upload closure."""
    data = bytearray()
    while True:
        chunk = await upload.read(min(65536, max_bytes - len(data) + 1))
        if not chunk:
            return bytes(data)
        data.extend(chunk)
        if len(data) > max_bytes:
            raise invalid_photo()


def normalize(data: bytes, max_bytes: int) -> tuple[bytes, str, str]:
    if not data or len(data) > max_bytes:
        raise invalid_photo()
    try:
        with DECODE_LOCK, warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(data)) as image:
                kind = image.format
                if kind not in FORMATS or image.width * image.height > MAX_PIXELS or getattr(image, "n_frames", 1) != 1:
                    raise invalid_photo()
                image.verify()
            with Image.open(io.BytesIO(data)) as image:
                image.load()
                oriented = ImageOps.exif_transpose(image)
                mode = "RGBA" if "A" in oriented.getbands() or "transparency" in oriented.info else "RGB"
                converted = oriented.convert(mode)
                # A new pixel-only image prevents EXIF/GPS, comments and profiles
                # from being copied implicitly by format-specific encoders.
                clean = Image.frombytes(mode, converted.size, converted.tobytes())
                output = io.BytesIO()
                clean.save(output, format=kind)
    except (UnidentifiedImageError, OSError, ValueError, SyntaxError,
            Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise invalid_photo() from None
    result = output.getvalue()
    if len(result) > max_bytes:
        raise invalid_photo()
    suffix, media_type = FORMATS[kind]
    return result, suffix, media_type


@dataclass(frozen=True)
class StoredPhoto:
    key: str
    media_type: str


class PhotoStore:
    def __init__(self, root: Path, max_bytes: int):
        if max_bytes < 1:
            raise ValueError("Photo byte limit must be positive")
        self.root, self.max_bytes = Path(root), max_bytes

    def _path(self, key: str) -> Path:
        if not KEY.fullmatch(key):
            raise DomainError("not_found", "Photo not found", 404)
        return self.root / key

    def save(self, data: bytes) -> StoredPhoto:
        content, suffix, media_type = normalize(data, self.max_bytes)
        self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
        key = f"{uuid4().hex}.{suffix}"
        path = self._path(key)
        # Exclusive creation must not overwrite (or follow) a preexisting entry.
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            with os.fdopen(fd, "wb") as target:
                target.write(content)
                target.flush()
                os.fsync(target.fileno())
        except BaseException:
            path.unlink(missing_ok=True)
            raise
        return StoredPhoto(key, media_type)

    def load(self, key: str) -> tuple[bytes, str]:
        path = self._path(key)
        try:
            fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        except OSError:
            raise DomainError("not_found", "Photo not found", 404) from None
        with os.fdopen(fd, "rb") as source:
            if not stat.S_ISREG(os.fstat(source.fileno()).st_mode):
                raise DomainError("not_found", "Photo not found", 404)
            content = source.read(self.max_bytes + 1)
        if not content or len(content) > self.max_bytes:
            raise DomainError("not_found", "Photo not found", 404)
        media_type = next(mime for suffix, mime in FORMATS.values() if key.endswith("." + suffix))
        return content, media_type

    def delete(self, key: str):
        self._path(key).unlink(missing_ok=True)
