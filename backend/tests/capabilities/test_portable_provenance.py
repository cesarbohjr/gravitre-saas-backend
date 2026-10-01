import pytest

from app.capabilities.provenance import bundle_digest, normalize_github_repository_url


def test_normalizes_github_repository_url() -> None:
    assert normalize_github_repository_url("https://github.com/acme/capabilities.git") == "https://github.com/acme/capabilities"


def test_rejects_arbitrary_remote_source() -> None:
    with pytest.raises(ValueError):
        normalize_github_repository_url("https://example.com/acme/repo")


def test_bundle_digest_is_stable_across_input_order() -> None:
    a = bundle_digest({"b.txt": "2", "a.txt": "1"})
    b = bundle_digest({"a.txt": "1", "b.txt": "2"})
    assert a == b
