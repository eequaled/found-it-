import hashlib
import hmac
import secrets


def token_hash(raw: str) -> bytes:
    return hashlib.sha256(raw.encode("utf-8")).digest()


def issue_token() -> tuple[str, bytes]:
    raw = secrets.token_urlsafe(32)
    return raw, token_hash(raw)


def token_matches(raw: str | None, expected: bytes | memoryview) -> bool:
    if raw is None or not 1 <= len(raw) <= 128:
        return False
    return hmac.compare_digest(token_hash(raw), bytes(expected))
