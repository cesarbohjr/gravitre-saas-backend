"""Public GitHub marketplace discovery for portable capabilities.

Sync is discovery-only. It never installs packages or executes repository code.
Private repositories require a future org-owned GitHub connector path.
"""
from __future__ import annotations

import base64
from typing import Any
from urllib.parse import urlparse

import httpx

from app.capabilities.importers import import_file_bundle
from app.capabilities.provenance import bundle_digest, normalize_github_repository_url

MAX_TREE_FILES = 1200
MAX_CANDIDATES = 100
MAX_PACKAGE_FILES = 80
TEXT_SUFFIXES = (".md", ".txt", ".json", ".yaml", ".yml")
PACKAGE_MARKERS = {
    "skill.md",
    "plugin.json",
    ".codex-plugin/plugin.json",
    ".claude-plugin/plugin.json",
    ".mcp.json",
    "mcp.json",
    "gravitre-plugin.json",
}


def _repo_parts(repository_url: str) -> tuple[str, str]:
    normalized = normalize_github_repository_url(repository_url)
    path = urlparse(normalized).path.strip("/")
    owner, repo = path.split("/", 1)
    return owner, repo


def _package_root(path: str) -> str | None:
    normalized = path.strip("/")
    lower = normalized.lower()
    for marker in PACKAGE_MARKERS:
        if lower == marker:
            return ""
        suffix = "/" + marker
        if lower.endswith(suffix):
            return normalized[: -len(suffix)]
    return None


async def _github_json(client: httpx.AsyncClient, url: str) -> Any:
    response = await client.get(url, headers={"Accept": "application/vnd.github+json"})
    if response.status_code == 404:
        raise ValueError("GitHub repository or branch not found, or repository is private")
    response.raise_for_status()
    return response.json()


async def discover_public_github_packages(
    *,
    repository_url: str,
    branch: str = "main",
    root_path: str = "",
) -> list[dict[str, Any]]:
    owner, repo = _repo_parts(repository_url)
    base = f"https://api.github.com/repos/{owner}/{repo}"
    root = root_path.strip().strip("/")
    async with httpx.AsyncClient(timeout=20.0, follow_redirects=False) as client:
        tree = await _github_json(client, f"{base}/git/trees/{branch}?recursive=1")
        rows = list(tree.get("tree") or [])
        if len(rows) > MAX_TREE_FILES:
            raise ValueError("Marketplace repository exceeds discovery file limit")

        roots: set[str] = set()
        for row in rows:
            if row.get("type") != "blob":
                continue
            path = str(row.get("path") or "").strip("/")
            if root and not (path == root or path.startswith(root + "/")):
                continue
            package_root = _package_root(path)
            if package_root is not None:
                roots.add(package_root)
            if len(roots) >= MAX_CANDIDATES:
                break

        candidates: list[dict[str, Any]] = []
        for package_root in sorted(roots):
            package_files = [
                str(row.get("path") or "")
                for row in rows
                if row.get("type") == "blob"
                and (
                    (not package_root and "/" not in str(row.get("path") or ""))
                    or (package_root and str(row.get("path") or "").startswith(package_root + "/"))
                )
                and str(row.get("path") or "").lower().endswith(TEXT_SUFFIXES)
            ][:MAX_PACKAGE_FILES]
            files: dict[str, str] = {}
            for path in package_files:
                payload = await _github_json(
                    client,
                    f"{base}/contents/{path}?ref={branch}",
                )
                if not isinstance(payload, dict) or payload.get("encoding") != "base64":
                    continue
                raw = base64.b64decode(str(payload.get("content") or "").encode("ascii"))
                if len(raw) > 300_000:
                    continue
                relative = path[len(package_root) + 1 :] if package_root else path
                files[relative] = raw.decode("utf-8", errors="replace")

            if not files:
                continue
            try:
                bundle = import_file_bundle(files)
            except ValueError:
                continue
            candidates.append(
                {
                    "packagePath": package_root or ".",
                    "files": files,
                    "manifest": bundle.manifest,
                    "inspection": bundle.inspection.as_dict(),
                    "contentDigest": bundle_digest(files),
                }
            )
        return candidates
