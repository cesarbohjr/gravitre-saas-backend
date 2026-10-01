from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.capabilities.provenance import inert_snapshot_digest
from app.marketplace.publish import (
    MarketplacePublishError,
    _assert_capability_provenance_current,
)


ORG_ID = "org-1"
PACKAGE_ID = "pkg-1"

MANIFEST = {"name": "Trusted skill", "license": "MIT"}
RESOURCES = [
    {
        "path": "SKILL.md",
        "kind": "reference",
        "content": "Use evidence.",
        "executable": False,
    }
]


def _client_with_package(package: dict) -> MagicMock:
    table = MagicMock()
    table.select.return_value = table
    table.eq.return_value = table
    table.limit.return_value = table
    table.execute.return_value = MagicMock(data=[package])
    client = MagicMock()
    client.table.return_value = table
    return client


def _package(**overrides) -> dict:
    row = {
        "id": PACKAGE_ID,
        "org_id": ORG_ID,
        "status": "installed",
        "content_digest": "sha256:" + "b" * 64,
        "manifest": MANIFEST,
        "license_policy": "allow",
        "risk_level": "low",
        "security_scan": {"blocked": False, "risk": "low"},
        "signature_status": "verified",
        "publisher_trusted": True,
        "publisher_verified": False,
        "source_uri": "trusted-package.zip",
        "source_commit_sha": None,
        "source_package_path": None,
    }
    row.update(overrides)
    return row


def _asset(*, mode: str = "trusted_signature", snapshot_digest: str | None = None) -> dict:
    return {
        "id": "asset-1",
        "asset_type": "capability_package",
        "org_id": ORG_ID,
        "config": {
            "source_package_id": PACKAGE_ID,
            "provenance_mode": mode,
            "repository_url": None,
            "commit_sha": None,
            "package_path": "",
            "content_digest": "sha256:" + "b" * 64,
            "snapshot_digest": snapshot_digest
            or inert_snapshot_digest(manifest=MANIFEST, resources=RESOURCES),
            "signature_status": "verified",
            "publisher_trust_scope": "organization",
        },
    }


def test_publish_gate_accepts_current_trusted_signed_package() -> None:
    client = _client_with_package(_package())
    with patch(
        "app.marketplace.publish.list_package_resources",
        return_value=RESOURCES,
    ):
        _assert_capability_provenance_current(client, _asset())


def test_publish_gate_rejects_revoked_signed_publisher_trust() -> None:
    client = _client_with_package(
        _package(publisher_trusted=False, publisher_verified=False)
    )
    with patch(
        "app.marketplace.publish.list_package_resources",
        return_value=RESOURCES,
    ):
        with pytest.raises(MarketplacePublishError, match="trust was revoked"):
            _assert_capability_provenance_current(client, _asset())


def test_publish_gate_rejects_source_snapshot_drift() -> None:
    changed_resources = [
        {
            "path": "SKILL.md",
            "kind": "reference",
            "content": "Changed after draft.",
            "executable": False,
        }
    ]
    client = _client_with_package(_package())
    with patch(
        "app.marketplace.publish.list_package_resources",
        return_value=changed_resources,
    ):
        with pytest.raises(MarketplacePublishError, match="snapshot changed"):
            _assert_capability_provenance_current(client, _asset())


def test_publish_gate_rejects_git_commit_drift() -> None:
    package = _package(
        signature_status="unsigned",
        publisher_trusted=False,
        source_uri="https://github.com/acme/capabilities@" + "a" * 40 + "#/skills/seo",
        source_commit_sha="c" * 40,
        source_package_path="skills/seo",
    )
    asset = _asset(mode="git_pinned")
    asset["config"].update(
        {
            "repository_url": "https://github.com/acme/capabilities",
            "commit_sha": "a" * 40,
            "package_path": "skills/seo",
            "signature_status": "unsigned",
            "publisher_trust_scope": "none",
        }
    )
    client = _client_with_package(package)
    with patch(
        "app.marketplace.publish.list_package_resources",
        return_value=RESOURCES,
    ):
        with pytest.raises(MarketplacePublishError, match="commit changed"):
            _assert_capability_provenance_current(client, asset)
