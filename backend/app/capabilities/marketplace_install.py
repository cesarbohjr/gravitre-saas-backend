"""Install source-pinned portable capabilities from Gravitre Marketplace."""
from __future__ import annotations

from pathlib import PurePosixPath
from typing import Any
from urllib.parse import urlparse

import httpx

from app.capabilities.importers import MAX_FILES, RESOURCE_SUFFIXES, SCRIPT_SUFFIXES, import_file_bundle
from app.capabilities.packages import inspect_package, installation_allowed
from app.capabilities.provenance import bundle_digest, inert_snapshot_digest, normalize_github_repository_url
from app.capabilities.repository import install_package, record_package_version, replace_package_resources

_MAX_PACKAGE_FILES = min(MAX_FILES, 100)
_ALLOWED_SUFFIXES = set(RESOURCE_SUFFIXES) | set(SCRIPT_SUFFIXES)


class CapabilityMarketplaceInstallError(ValueError):
    pass


def _repo_parts(repository_url: str) -> tuple[str, str]:
    normalized = normalize_github_repository_url(repository_url)
    path = urlparse(normalized).path.strip("/")
    owner, repo = path.split("/", 1)
    return owner, repo


def _github_headers(access_token: str | None = None, *, raw: bool = False) -> dict[str, str]:
    headers = {
        "Accept": "application/vnd.github.raw+json" if raw else "application/vnd.github+json",
        "User-Agent": "Gravitre-Capability-Marketplace",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if access_token:
        headers["Authorization"] = f"Bearer {access_token}"
    return headers


def fetch_pinned_capability_files(
    *,
    repository_url: str,
    commit_sha: str,
    package_path: str,
    access_token: str | None = None,
) -> dict[str, str]:
    owner, repo = _repo_parts(repository_url)
    commit = str(commit_sha or "").strip().lower()
    if len(commit) != 40 or any(ch not in "0123456789abcdef" for ch in commit):
        raise CapabilityMarketplaceInstallError("Capability package source must use an exact 40-character Git commit SHA")
    root = str(package_path or "").strip().strip("/")
    base = f"https://api.github.com/repos/{owner}/{repo}"

    with httpx.Client(timeout=20.0, follow_redirects=False, headers=_github_headers(access_token)) as client:
        commit_response = client.get(f"{base}/git/commits/{commit}")
        if commit_response.status_code in {401, 403, 404}:
            raise CapabilityMarketplaceInstallError("Pinned capability source is unavailable")
        commit_response.raise_for_status()
        tree_sha = str(((commit_response.json() or {}).get("tree") or {}).get("sha") or "")
        if not tree_sha:
            raise CapabilityMarketplaceInstallError("Pinned capability commit has no readable tree")

        tree_response = client.get(f"{base}/git/trees/{tree_sha}", params={"recursive": "1"})
        tree_response.raise_for_status()
        rows = list((tree_response.json() or {}).get("tree") or [])
        prefix = root + "/" if root else ""
        paths = [
            str(row.get("path") or "")
            for row in rows
            if row.get("type") == "blob"
            and (
                (not root)
                or str(row.get("path") or "") == root
                or str(row.get("path") or "").startswith(prefix)
            )
            and (
                PurePosixPath(str(row.get("path") or "")).suffix.lower() in _ALLOWED_SUFFIXES
                or PurePosixPath(str(row.get("path") or "")).name.lower()
                in {"skill.md", "plugin.json", "gravitre-plugin.json", ".mcp.json", "mcp.json"}
            )
        ][: _MAX_PACKAGE_FILES]

        files: dict[str, str] = {}
        for path in paths:
            response = client.get(
                f"{base}/contents/{path}",
                params={"ref": commit},
                headers=_github_headers(access_token, raw=True),
            )
            if response.status_code != 200:
                continue
            relative = path[len(prefix):] if prefix and path.startswith(prefix) else path
            files[relative] = response.text

    if not files:
        raise CapabilityMarketplaceInstallError("Pinned capability package contains no supported files")
    return files


def resolve_org_github_token(
    client: Any,
    *,
    org_id: str,
    settings: Any,
    environment_name: str,
) -> str | None:
    try:
        from app.connectors.connector_tool_auth import resolve_github_access_token
        from app.connectors.repository import get_connector_by_type

        connector = get_connector_by_type(
            client,
            org_id,
            "github",
            environment_name=environment_name,
        )
        if not connector:
            return None
        return resolve_github_access_token(
            client,
            org_id,
            str(connector.get("id") or ""),
            settings,
            environment_name=environment_name,
        )
    except Exception:
        return None


def _resource_row_to_dict(row: Any) -> dict[str, Any]:
    if isinstance(row, dict):
        return dict(row)
    if hasattr(row, "model_dump"):
        dumped = row.model_dump(mode="json")
        return dumped if isinstance(dumped, dict) else {}
    values = vars(row) if hasattr(row, "__dict__") else {}
    return dict(values) if isinstance(values, dict) else {}


def install_marketplace_capability_package(
    client: Any,
    *,
    org_id: str,
    actor_id: str,
    asset: dict[str, Any],
    config: Any,
    settings: Any,
    environment_name: str,
) -> dict[str, Any]:
    raw_manifest = getattr(config, "manifest", {})
    manifest = raw_manifest if isinstance(raw_manifest, dict) else {}
    raw_resources = getattr(config, "resources", []) or []
    resource_rows = [_resource_row_to_dict(row) for row in raw_resources]
    skill_md = next(
        (
            str(row.get("content") or "")
            for row in resource_rows
            if str(row.get("path") or "").lower().endswith("skill.md")
            and not bool(row.get("executable"))
            and row.get("content")
        ),
        None,
    )

    # New Marketplace assets are immutable inert snapshots. Older assets that
    # predate snapshotting may fall back to their exact Git commit.
    if manifest or resource_rows:
        actual_snapshot_digest = inert_snapshot_digest(
            manifest=manifest,
            resources=resource_rows,
        )
        expected_snapshot_digest = str(getattr(config, "snapshot_digest", "") or "")
        if not expected_snapshot_digest or actual_snapshot_digest != expected_snapshot_digest:
            raise CapabilityMarketplaceInstallError(
                "Capability Marketplace snapshot digest does not match the reviewed artifact"
            )
        inspection = inspect_package(manifest, skill_md=skill_md)
        raw_security_scan = getattr(config, "security_scan", {})
        security_scan = raw_security_scan if isinstance(raw_security_scan, dict) else {}
        if (
            not installation_allowed(inspection)
            or bool(security_scan.get("blocked"))
            or str(getattr(config, "license_policy", "") or "") == "block"
            or str(getattr(config, "risk_level", "") or "") == "blocked"
        ):
            raise CapabilityMarketplaceInstallError(
                "Capability package does not pass the destination organization's current security/license policy"
            )
        resources = [
            {
                "path": str(row.get("path") or ""),
                "kind": str(row.get("kind") or "reference"),
                "content": None
                if bool(row.get("executable")) or str(row.get("kind") or "") == "script"
                else row.get("content"),
                "executable": bool(row.get("executable")),
            }
            for row in resource_rows
            if str(row.get("path") or "").strip()
        ]
        source_digest = str(config.content_digest)
    else:
        access_token = resolve_org_github_token(
            client,
            org_id=org_id,
            settings=settings,
            environment_name=environment_name,
        )
        files = fetch_pinned_capability_files(
            repository_url=str(config.repository_url),
            commit_sha=str(config.commit_sha),
            package_path=str(config.package_path or ""),
            access_token=access_token,
        )
        actual_digest = bundle_digest(files)
        if actual_digest != str(config.content_digest):
            raise CapabilityMarketplaceInstallError(
                "Capability package digest does not match the published Marketplace artifact"
            )
        bundle = import_file_bundle(files)
        if not installation_allowed(bundle.inspection) or bool(bundle.security_scan.get("blocked")):
            raise CapabilityMarketplaceInstallError(
                "Capability package no longer passes Gravitre security/license policy"
            )
        inspection = bundle.inspection
        manifest = bundle.manifest
        security_scan = bundle.security_scan
        resources = list(bundle.resources)
        source_digest = actual_digest

    publisher_verified = False
    publisher_name: str | None = None
    marketplace_publisher_id: str | None = None
    publisher_id = str(asset.get("publisher_id") or "")
    if publisher_id:
        try:
            row = (
                client.table("marketplace_publishers")
                .select("id,display_name,verified")
                .eq("id", publisher_id)
                .limit(1)
                .execute()
            )
            if row.data:
                marketplace_publisher_id = str(row.data[0].get("id") or "") or None
                publisher_name = str(row.data[0].get("display_name") or "") or None
                publisher_verified = bool(row.data[0].get("verified"))
        except Exception:
            pass

    installed = install_package(
        client,
        org_id=org_id,
        user_id=actor_id,
        inspection=inspection,
        manifest=manifest,
        source_type="marketplace",
        source_uri=(
            f"{config.repository_url}@{config.commit_sha}#/{config.package_path or ''}"
            if config.repository_url and config.commit_sha
            else f"marketplace:{asset.get('slug') or asset.get('id')}"
        ),
        source_commit_sha=str(config.commit_sha or "") or None,
        source_package_path=str(config.package_path or "") or None,
        publisher_name=publisher_name,
        publisher_trusted=publisher_verified,
        publisher_trust_scope="marketplace_verified" if publisher_verified else "none",
        publisher_verified=publisher_verified,
        marketplace_publisher_id=marketplace_publisher_id,
        signature_status=str(config.signature_status or "unsigned"),
        content_digest=source_digest,
        security_scan=security_scan,
    )
    package_id = str(installed.get("id") or "")
    if not package_id:
        raise CapabilityMarketplaceInstallError("Capability package install did not return an id")

    replace_package_resources(
        client,
        package_id=package_id,
        org_id=org_id,
        resources=resources,
    )
    record_package_version(
        client,
        org_id=org_id,
        package=installed,
        resources=resources,
        user_id=actor_id,
    )
    package_status = str(installed.get("status") or "installed")
    return {
        "entityType": "capability_package",
        "entityId": package_id,
        "capabilityPackageId": package_id,
        "securityRisk": installed.get("risk_level"),
        "publisherVerified": publisher_verified,
        "status": package_status,
        "requiresReview": package_status == "quarantined",
        "mcpPrepared": False,
    }
