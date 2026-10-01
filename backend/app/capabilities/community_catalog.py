"""Admin-only federation of official portable capability catalogs.

Discovery is read-only. Nothing from an external catalog is installed or made
runtime-visible until an org admin stages the source, reviews candidates, and
explicitly installs/approves them through the existing Gravitre governance path.
"""
from __future__ import annotations

from dataclasses import dataclass
from time import monotonic
from typing import Any

import httpx

from app.capabilities.github_sync import _package_root

_CACHE_TTL_SECONDS = 300.0
_cache: dict[str, tuple[float, list[dict[str, Any]]]] = {}


@dataclass(frozen=True)
class CommunityCatalogSource:
    key: str
    name: str
    publisher: str
    repository_url: str
    owner: str
    repo: str
    branch: str
    root_path: str
    kind: str = "skill"
    trust: str = "official"


OFFICIAL_COMMUNITY_SOURCES: tuple[CommunityCatalogSource, ...] = (
    CommunityCatalogSource(
        key="openai-skills",
        name="OpenAI Skills",
        publisher="OpenAI",
        repository_url="https://github.com/openai/skills",
        owner="openai",
        repo="skills",
        branch="main",
        root_path="skills/.curated",
    ),
    CommunityCatalogSource(
        key="anthropic-skills",
        name="Anthropic Skills",
        publisher="Anthropic",
        repository_url="https://github.com/anthropics/skills",
        owner="anthropics",
        repo="skills",
        branch="main",
        root_path="skills",
    ),
)


def community_source(source_key: str) -> CommunityCatalogSource | None:
    return next((row for row in OFFICIAL_COMMUNITY_SOURCES if row.key == source_key), None)


async def _fetch_source_index(source: CommunityCatalogSource) -> list[dict[str, Any]]:
    cached = _cache.get(source.key)
    now = monotonic()
    if cached and now - cached[0] < _CACHE_TTL_SECONDS:
        return cached[1]

    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "Gravitre-Capability-Discovery/1.0",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    async with httpx.AsyncClient(
        base_url="https://api.github.com",
        headers=headers,
        timeout=httpx.Timeout(12.0),
        follow_redirects=False,
    ) as client:
        branch_response = await client.get(
            f"/repos/{source.owner}/{source.repo}/branches/{source.branch}"
        )
        branch_response.raise_for_status()
        branch_payload = branch_response.json() or {}
        commit_sha = str(((branch_payload.get("commit") or {}).get("sha")) or "")
        tree_url = str(((branch_payload.get("commit") or {}).get("commit") or {}).get("tree", {}).get("url") or "")
        if tree_url:
            tree_sha = tree_url.rstrip("/").split("/")[-1]
        else:
            commit_response = await client.get(
                f"/repos/{source.owner}/{source.repo}/git/commits/{commit_sha}"
            )
            commit_response.raise_for_status()
            tree_sha = str(((commit_response.json() or {}).get("tree") or {}).get("sha") or "")
        if not commit_sha or not tree_sha:
            raise ValueError(f"{source.name} could not be resolved to an immutable commit")

        tree_response = await client.get(
            f"/repos/{source.owner}/{source.repo}/git/trees/{tree_sha}",
            params={"recursive": "1"},
        )
        tree_response.raise_for_status()
        tree_rows = list((tree_response.json() or {}).get("tree") or [])

    prefix = source.root_path.strip("/")
    roots: list[str] = []
    for row in tree_rows:
        path = str(row.get("path") or "")
        if row.get("type") != "blob" or not path:
            continue
        if prefix and not (path == prefix or path.startswith(prefix + "/")):
            continue
        root = _package_root(path)
        if root is None:
            continue
        if prefix and not (root == prefix or root.startswith(prefix + "/")):
            continue
        if root not in roots:
            roots.append(root)

    items = [
        {
            "id": f"{source.key}:{root}",
            "name": root.rsplit("/", 1)[-1] if root else source.repo,
            "kind": source.kind,
            "publisher": source.publisher,
            "sourceKey": source.key,
            "sourceName": source.name,
            "repositoryUrl": source.repository_url,
            "branch": source.branch,
            "packagePath": root or ".",
            "sourceUrl": f"{source.repository_url}/tree/{source.branch}/{root}" if root else source.repository_url,
            "trust": source.trust,
            "status": "available_for_review",
            "runtimeEnabled": False,
            "commitSha": commit_sha,
        }
        for root in roots
    ]
    _cache[source.key] = (now, items)
    return items


async def list_official_community_catalog(
    *,
    query: str | None = None,
    source_key: str | None = None,
) -> dict[str, Any]:
    sources = [
        row for row in OFFICIAL_COMMUNITY_SOURCES
        if not source_key or row.key == source_key
    ]
    q = (query or "").strip().lower()
    items: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    for source in sources:
        try:
            rows = await _fetch_source_index(source)
        except Exception as exc:
            errors.append({"sourceKey": source.key, "message": str(exc)[:300]})
            continue
        if q:
            rows = [
                row for row in rows
                if q in str(row.get("name") or "").lower()
                or q in str(row.get("publisher") or "").lower()
                or q in str(row.get("packagePath") or "").lower()
            ]
        items.extend(rows)

    return {
        "items": items,
        "sources": [
            {
                "key": row.key,
                "name": row.name,
                "publisher": row.publisher,
                "repositoryUrl": row.repository_url,
                "branch": row.branch,
                "rootPath": row.root_path,
                "kind": row.kind,
                "trust": row.trust,
            }
            for row in sources
        ],
        "errors": errors,
        "adminOnly": True,
        "activationPolicy": "review_required",
    }
