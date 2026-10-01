from unittest.mock import patch

import pytest
from pydantic import ValidationError

from app.capabilities.marketplace_install import install_marketplace_capability_package
from app.marketplace.schemas import CapabilityPackageAssetConfig


def _config() -> CapabilityPackageAssetConfig:
    return CapabilityPackageAssetConfig(
        manifest={"name": "SEO analyst", "license": "MIT"},
        resources=[
            {
                "path": "SKILL.md",
                "kind": "reference",
                "content": "---\nname: seo-analyst\ndescription: Audit SEO\n---\nUse evidence.",
                "executable": False,
            },
            {
                "path": "scripts/run.py",
                "kind": "script",
                "content": None,
                "executable": True,
            },
        ],
        package_format="agent_skill",
        license="MIT",
        license_policy="allow",
        risk_level="low",
        signature_status="unsigned",
        content_digest="sha256:reviewed-snapshot",
        repository_url="https://github.com/acme/capabilities",
        commit_sha="a" * 40,
        package_path="skills/seo",
        security_scan={"risk": "low", "blocked": False},
    )


def test_marketplace_snapshot_rejects_embedded_executable_content() -> None:
    with pytest.raises(ValidationError):
        CapabilityPackageAssetConfig(
            manifest={"name": "unsafe", "license": "MIT"},
            resources=[
                {
                    "path": "scripts/run.py",
                    "kind": "script",
                    "content": "print('must not ship')",
                    "executable": True,
                }
            ],
            package_format="agent_skill",
            license_policy="allow",
            risk_level="low",
            content_digest="sha256:test",
        )


def test_marketplace_install_prefers_inert_snapshot_and_does_not_refetch_source() -> None:
    installed = {
        "id": "pkg-1",
        "name": "SEO analyst",
        "status": "installed",
        "risk_level": "low",
        "version": "0.0.0",
        "content_digest": "sha256:reviewed-snapshot",
    }
    with (
        patch(
            "app.capabilities.marketplace_install.fetch_pinned_capability_files",
            side_effect=AssertionError("snapshot install must not refetch GitHub"),
        ),
        patch(
            "app.capabilities.marketplace_install.install_package",
            return_value=installed,
        ) as install,
        patch("app.capabilities.marketplace_install.replace_package_resources") as resources,
        patch("app.capabilities.marketplace_install.record_package_version") as version,
    ):
        result = install_marketplace_capability_package(
            object(),
            org_id="org-1",
            actor_id="user-1",
            asset={"id": "asset-1", "slug": "seo-analyst"},
            config=_config(),
            settings=object(),
            environment_name="production",
        )

    assert result["capabilityPackageId"] == "pkg-1"
    assert result["requiresReview"] is False
    assert result["mcpPrepared"] is False
    assert install.call_args.kwargs["source_type"] == "marketplace"
    saved_resources = resources.call_args.kwargs["resources"]
    script = next(row for row in saved_resources if row["kind"] == "script")
    assert script["content"] is None
    version.assert_called_once()


def test_marketplace_install_surfaces_destination_quarantine() -> None:
    installed = {
        "id": "pkg-2",
        "name": "SEO analyst",
        "status": "quarantined",
        "risk_level": "high",
        "version": "0.0.0",
    }
    with (
        patch("app.capabilities.marketplace_install.install_package", return_value=installed),
        patch("app.capabilities.marketplace_install.replace_package_resources"),
        patch("app.capabilities.marketplace_install.record_package_version"),
    ):
        result = install_marketplace_capability_package(
            object(),
            org_id="org-1",
            actor_id="user-1",
            asset={"id": "asset-1", "slug": "seo-analyst"},
            config=_config(),
            settings=object(),
            environment_name="production",
        )
    assert result["status"] == "quarantined"
    assert result["requiresReview"] is True
