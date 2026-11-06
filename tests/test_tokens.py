import pytest

from app.security import issue_token, token_hash, token_matches


def test_tracking_tokens_are_random_and_only_hashes_are_stored():
    raw, digest = issue_token()
    other, _ = issue_token()
    assert raw != other and len(raw) == 43
    assert len(digest) == 32 and digest == token_hash(raw)
    assert token_matches(raw, digest)
    assert token_matches(raw, memoryview(digest))


@pytest.mark.parametrize("bad", [None, "", "wrong-token", "x" * 129])
def test_invalid_tokens_never_match(bad):
    _, digest = issue_token()
    assert not token_matches(bad, digest)
