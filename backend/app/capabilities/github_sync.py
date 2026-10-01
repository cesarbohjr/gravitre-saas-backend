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

from app.capabilities.importers import import_file_bundle
from app.capabilities.provenance import bundle_digest, normalize_github_repository_url
from app.capabilities.repository import install_package, replace_package_resources

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
) -> list[GithubPackageBundle]:
    owner, repo = _repo_parts(repository_url)
    root_prefix = root_path.strip().strip("/")
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "Gravitre-Capability-Sync",
        "X-GitHub-Api-Version": "2022-11-28",
    }
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
) -> dict[str, Any]:
    bundles = await discover_public_github_packages(
        str(source.get("repository_url") or ""),
        branch=str(source.get("branch") or "main"),
        root_path=str(source.get("root_path") or ""),
    )
    approval_required = bool(source.get("approval_required", True))
    installed: list[dict[str, Any]] = []
    rejected: list[dict[str, str]] = []

    for item in bundles:
        bundle = import_file_bundle(item.files)
        inspection = bundle.inspection
        if inspection.license_policy == "block" or inspection.risk == "blocked":
            rejected.append({"root": item.root, "name": inspection.name, "reason": "blocked_by_policy"})
            continue
        row = install_package(
            client,
            org_id=org_id,
            user_id=user_id,
            inspection=inspection,
            manifest=bundle.manifest,
            source_type="marketplace",
            source_uri=f"{source.get('repository_url')}#/{item.root}",
            marketplace_source_id=str(source.get("id") or "") or None,
            publisher_name=str(source.get("repository_url") or "").removeprefix("https://github.com/").split("/", 1)[0] or None,
            publisher_verified=False,
            signature_status="unsigned",
            content_digest=bundle_digest(item.files),
            initial_status="quarantined" if approval_required or inspection.risk == "high" else "installed",
        )
        package_id = str(row.get("id") or "")
        if package_id:
            replace_package_resources(
                client,
                package_id=package_id,
                org_id=org_id,
                resources=list(bundle.resources),
            )
        installed.append(row)

    return {
        "discovered": len(bundles),
        "ingested": len(installed),
        "rejected": rejected,
        "packages": installed,
        "approvalRequired": approval_required,
    }
