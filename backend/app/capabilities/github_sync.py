"""Safe sync for public GitHub capability marketplaces.

Remote hosts are fixed to api.github.com/raw.githubusercontent.com. Private
repositories are intentionally not guessed at; they require an explicit
credential integration before sync can be enabled.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Any

import httpx

from app.config import Settings

from app.capabilities.importers import import_file_bundle
from app.capabilities.provenance import bundle_digest, normalize_github_repository_url
from app.capabilities.repository import upsert_marketplace_candidate

TEXT_SUFFIXES = {".md", ".txt", ".json", ".yaml", ".yml", ".py", ".js", ".ts", ".sh", ".bash", ".ps1"}
MANIFEST_NAMES = {
    "gravitre-plugin.json",
    "plugin.json",
    ".mcp.json",
    "mcp.json",
}
MAX_PACKAGES_PER_SYNC = 50
MAX_FILES_PER_PACKAGE = 80


@dataclass(frozen=True)
class GithubPackageBundle:
    root: str
    files: dict[str, str]


def _repo_parts(repository_url: str) -> tuple[str, str]:
    normalized = normalize_github_repository_url(repository_url)
    parts = normalized.removeprefix("https://github.com/").split("/", 1)
    return parts[0], parts[1]


def _package_root(path: str) -> str | None:
    p = PurePosixPath(path)
    lower = path.lower()
    if lower.endswith("/.codex-plugin/plugin.json") or lower == ".codex-plugin/plugin.json":
        return str(p.parent.parent) if str(p.parent.parent) != "." else ""
    if lower.endswith("/.claude-plugin/plugin.json") or lower == ".claude-plugin/plugin.json":
        return str(p.parent.parent) if str(p.parent.parent) != "." else ""
    if p.name.lower() in MANIFEST_NAMES or p.name.lower() == "skill.md":
        parent = str(p.parent)
        return "" if parent == "." else parent
    return None


async def discover_public_github_packages(
    repository_url: str,
    *,
    branch: str = "main",
    root_path: str = "",
    timeout_s: float = 12.0,
    access_token: str | None = None,
) -> list[GithubPackageBundle]:
    owner, repo = _repo_parts(repository_url)
    root_prefix = root_path.strip().strip("/")
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "Gravitre-Capability-Sync",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if access_token:
        headers["Authorization"] = f"Bearer {access_token}"
    async with httpx.AsyncClient(
        base_url="https://api.github.com",
        headers=headers,
        timeout=timeout_s,
        follow_redirects=False,
    ) as client:
        tree = await client.get(f"/repos/{owner}/{repo}/git/trees/{branch}", params={"recursive": "1"})
        if tree.status_code in {401, 403, 404}:
            raise ValueError(
                "GitHub repository is unavailable to anonymous sync; connect an authorized GitHub source for private repositories."
            )
        tree.raise_for_status()
        rows = list((tree.json() or {}).get("tree") or [])
        file_paths = [
            str(row.get("path") or "")
            for row in rows
            if row.get("type") == "blob" and str(row.get("path") or "")
        ]
        if root_prefix:
            file_paths = [
                p for p in file_paths
                if p == root_prefix or p.startswith(root_prefix + "/")
            ]

        roots: list[str] = []
        for path in file_paths:
            root = _package_root(path)
            if root is None:
                continue
            if root_prefix and not (root == root_prefix or root.startswith(root_prefix + "/")):
                continue
            if root not in roots:
                roots.append(root)
            if len(roots) >= MAX_PACKAGES_PER_SYNC:
                break

        packages: list[GithubPackageBundle] = []
        for root in roots:
            prefix = root + "/" if root else ""
            candidate_paths = [
                path for path in file_paths
                if path.startswith(prefix)
                and PurePosixPath(path).suffix.lower() in TEXT_SUFFIXES
            ][:MAX_FILES_PER_PACKAGE]
            files: dict[str, str] = {}
            for path in candidate_paths:
                relative = path[len(prefix):] if prefix else path
                response = await client.get(
                    f"/repos/{owner}/{repo}/contents/{path}",
                    params={"ref": branch},
                    headers={**headers, "Accept": "application/vnd.github.raw+json"},
                )
                if response.status_code != 200:
                    continue
                files[relative] = response.text
            if files:
                try:
                    import_file_bundle(files)
                except ValueError:
                    continue
                packages.append(GithubPackageBundle(root=root, files=files))
        return packages


async def sync_public_github_marketplace(
    client: Any,
    *,
    org_id: str,
    user_id: str,
    source: dict[str, Any],
    settings: Settings | None = None,
    environment_name: str = "production",
) -> dict[str, Any]:
    """Discover packages and stage them for review; never install during sync."""
    access_token: str | None = None
    if settings is not None:
        try:
            from app.connectors.connector_tool_auth import resolve_github_access_token
            from app.connectors.repository import get_connector_by_type

            connector = get_connector_by_type(
                client,
                org_id,
                "github",
                environment_name=environment_name,
            )
            if connector:
                access_token = resolve_github_access_token(
                    client,
                    org_id,
                    str(connector.get("id") or ""),
                    settings,
                    environment_name=environment_name,
                )
        except Exception:
            access_token = None

    bundles = await discover_public_github_packages(
        str(source.get("repository_url") or ""),
        branch=str(source.get("branch") or "main"),
        root_path=str(source.get("root_path") or ""),
        access_token=access_token,
    )
    staged: list[dict[str, Any]] = []
    rejected: list[dict[str, str]] = []

    for item in bundles:
        bundle = import_file_bundle(item.files)
        inspection = bundle.inspection
        if inspection.license_policy == "block" or inspection.risk == "blocked":
            rejected.append({"root": item.root, "name": inspection.name, "reason": "blocked_by_policy"})
            continue
        row = upsert_marketplace_candidate(
            client,
            org_id=org_id,
            source_id=str(source.get("id") or ""),
            package_path=item.root or ".",
            manifest=bundle.manifest,
            inspection=inspection.as_dict(),
            content_digest=bundle_digest(item.files),
            files=item.files,
        )
        staged.append(row)

    return {
        "discovered": len(bundles),
        "ingested": len(staged),
        "rejected": rejected,
        "candidates": staged,
        "approvalRequired": True,
        "installed": 0,
    }
