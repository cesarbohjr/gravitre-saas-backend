"""Read-only Agency Agents inventory and staged Marketplace asset adapter.

No database writes, no automatic publication, no new runtime authority.
PR #587 owns intelligence, personality, dialogue and voice integration.
"""
from __future__ import annotations

import json
from pathlib import Path

from app.marketplace.seed_catalog import CatalogAsset

INVENTORY = Path(__file__).with_name("agency_agents_inventory.json")
VALID_DISPOSITIONS = {"enrich_existing", "marketplace_agent", "marketplace_pack", "exclude"}


def load_agency_inventory(path: Path = INVENTORY) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema_version") != 1 or data.get("classification") != "proposed_only":
        raise ValueError("unapproved_or_invalid_inventory")
    if len(data.get("source_commit", "")) != 40:
        raise ValueError("unpinned_upstream")
    divisions = set(data.get("divisions", []))
    if not divisions or not data.get("agents"):
        raise ValueError("empty_inventory")
    slugs: set[str] = set()
    paths: set[str] = set()
    for agent in data["agents"]:
        slug, source = agent["slug"], agent["source_path"]
        if not slug.startswith("agency-") or slug in slugs or source in paths:
            raise ValueError("duplicate_or_invalid_agent")
        if agent["division"] not in divisions or not source.startswith(agent["division"] + "/"):
            raise ValueError("invalid_division")
        if agent["proposed_disposition"] not in VALID_DISPOSITIONS:
            raise ValueError("invalid_disposition")
        if agent["publication_status"] != "draft_unapproved":
            raise ValueError("unexpected_publication")
        if not agent["source_url"].startswith(
            f"https://github.com/{data['source_repo']}/blob/{data['source_commit']}/"
        ):
            raise ValueError("untrusted_source")
        slugs.add(slug)
        paths.add(source)
    return data


def preview_marketplace_candidates(path: Path = INVENTORY) -> list[CatalogAsset]:
    """Construct review-only catalog previews; never include in list_catalog_assets."""
    data = load_agency_inventory(path)
    result: list[CatalogAsset] = []
    for agent in data["agents"]:
        if agent["proposed_disposition"] != "marketplace_agent":
            continue
        result.append(CatalogAsset(
            slug=agent["slug"],
            title=agent["name"],
            description=agent["specialty"] or f"{agent['name']} specialist",
            asset_type="ai_agent",
            category="agents",
            department=agent["division"],
            config={
                "source": "agency_agents",
                "source_revision": data["source_commit"],
                "source_path": agent["source_path"],
                "publication_status": "draft_unapproved",
                "governance_review_required": agent["requires_governance_review"],
                "persona_key": agent["slug"],
            },
            tags=["agency-agents", agent["division"], "review-only"],
        ))
    return result


def approved_marketplace_candidates(*args, **kwargs):
    """Deliberately fail closed until product review and explicit release gating."""
    raise PermissionError("Agency Agents Marketplace packages are not approved for publication")
