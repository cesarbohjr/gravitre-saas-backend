import pytest

from app.capabilities.provenance import bundle_digest, inert_snapshot_digest, normalize_github_repository_url


def test_normalizes_github_repository_url() -> None:
    assert normalize_github_repository_url("https://github.com/acme/capabilities.git") == "https://github.com/acme/capabilities"


def test_rejects_arbitrary_remote_source() -> None:
    with pytest.raises(ValueError):
        normalize_github_repository_url("https://example.com/acme/repo")


def test_bundle_digest_is_stable_across_input_order() -> None:
    a = bundle_digest({"b.txt": "2", "a.txt": "1"})
    b = bundle_digest({"a.txt": "1", "b.txt": "2"})
    assert a == b


def test_signature_does_not_imply_publisher_trust() -> None:
    from app.capabilities.provenance import provenance_summary

    summary = provenance_summary(
        publisher_name="Acme",
        signature_status="verified",
    )
    assert summary["signatureStatus"] == "verified"
    assert summary["publisherVerified"] is False


def test_inert_snapshot_digest_is_stable_across_resource_order() -> None:
    manifest = {"name": "SEO skill", "license": "MIT"}
    first = inert_snapshot_digest(
        manifest=manifest,
        resources=[
            {"path": "b.md", "kind": "reference", "content": "B", "executable": False},
            {"path": "a.md", "kind": "reference", "content": "A", "executable": False},
        ],
    )
    second = inert_snapshot_digest(
        manifest=manifest,
        resources=[
            {"path": "a.md", "kind": "reference", "content": "A", "executable": False},
            {"path": "b.md", "kind": "reference", "content": "B", "executable": False},
        ],
    )
    assert first == second


def test_inert_snapshot_digest_ignores_executable_source_content() -> None:
    manifest = {"name": "Task"}
    safe = inert_snapshot_digest(
        manifest=manifest,
        resources=[
            {"path": "scripts/run.py", "kind": "script", "content": None, "executable": True}
        ],
    )
    supplied = inert_snapshot_digest(
        manifest=manifest,
        resources=[
            {"path": "scripts/run.py", "kind": "script", "content": "print('x')", "executable": True}
        ],
    )
    assert safe == supplied
