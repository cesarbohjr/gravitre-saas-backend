from app.capabilities.repository import package_version_conflicts


def test_same_version_rejects_different_digest() -> None:
    assert package_version_conflicts(
        {"content_digest": "sha256:old", "source_uri": "marketplace:a"},
        incoming_digest="sha256:new",
        incoming_source_uri="marketplace:a",
    )


def test_same_version_allows_identical_digest() -> None:
    assert not package_version_conflicts(
        {"content_digest": "sha256:same", "source_uri": "marketplace:a"},
        incoming_digest="sha256:same",
        incoming_source_uri="marketplace:a",
    )
