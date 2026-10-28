"""Read-only Agency Agents inventory and staged Marketplace asset adapter.

No database writes, no automatic publication, no new runtime authority.
PR #587 owns intelligence, personality, dialogue and voice integration.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from app.marketplace.seed_catalog import CatalogAsset

INVENTORY = Path(__file__).with_name("agency_agents_inventory.json")
VALID_DISPOSITIONS = {"enrich_existing", "marketplace_agent", "marketplace_pack", "exclude"}
SOURCE_REPO = "msitarzewski/agency-agents"

# Candidate destinations, not authorization or claims of functional equivalence.
# A missing seed pack remains explicitly absent; do not invent a new pack.
DIVISION_TARGETS = {
    "academic": ("Research", None, "agency"),
    "design": ("Marketing", "marketing-operations-pack", None),
    "engineering": ("Engineering", None, "engineering"),
    "finance": ("Finance", None, None),
    "game-development": ("Engineering", None, "engineering"),
    "gis": ("Research", None, "agency"),
    "healthcare": ("Research", None, "agency"),
    "marketing": ("Marketing", "marketing-operations-pack", None),
    "paid-media": ("Marketing", "marketing-operations-pack", None),
    "product": ("Marketing", "marketing-operations-pack", None),
    "project-management": ("Operations", "msp-operations-pack", "agency"),
    "research": ("Research", None, "agency"),
    "sales": ("Sales", "revenue-operations-pack", None),
    "security": ("Security", None, "security"),
    "spatial-computing": ("Engineering", None, "engineering"),
    "specialized": ("Operations", None, "agency"),
    "support": ("Support", "support-operations-pack", None),
    "testing": ("QA", None, "qa"),
}

# Explicit function-level overlap candidates override broad division routing.
FUNCTION_TARGETS = {
    "design-ui-designer": "marketing-designer",
    "marketing-content-creator": "content-writer",
    "marketing-seo-specialist": "seo-analyst",
    "sales-pipeline-analyst": "revenue-operations-agent",
    "sales-discovery-coach": "sdr-coach",
    "product-trend-researcher": "competitor-research-agent",
    "product-product-manager": "product-icp-strategist",
    "support-support-responder": "ticket-triage",
    "support-finance-tracker": "cfo-agent",
}


def load_agency_inventory(path: Path = INVENTORY) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema_version") != 1 or data.get("classification") != "proposed_only":
        raise ValueError("unapproved_or_invalid_inventory")
    if not isinstance(data.get("source_commit"), str) or not re.fullmatch(r"[0-9a-f]{40}", data["source_commit"]):
        raise ValueError("unpinned_upstream")
    if data.get("source_repo") != SOURCE_REPO:
        raise ValueError("untrusted_source_repo")
    divisions = set(data.get("divisions", []))
    if not divisions or not data.get("agents"):
        raise ValueError("empty_inventory")
    slugs: set[str] = set()
    paths: set[str] = set()
    for agent in data["agents"]:
        slug, source = agent["slug"], agent["source_path"]
        if not re.fullmatch(r"agency-[a-z0-9]+(?:-[a-z0-9]+)*", slug) or slug in slugs or source in paths:
            raise ValueError("duplicate_or_invalid_agent")
        if not re.fullmatch(r"[a-z0-9/-]+\.md", source) or ".." in source:
            raise ValueError("unsafe_source_path")
        if agent["division"] not in divisions or not source.startswith(agent["division"] + "/"):
            raise ValueError("invalid_division")
        if agent["proposed_disposition"] not in VALID_DISPOSITIONS:
            raise ValueError("invalid_disposition")
        if agent["publication_status"] != "draft_unapproved":
            raise ValueError("unexpected_publication")
        if agent["source_url"] != f"https://github.com/{SOURCE_REPO}/blob/{data['source_commit']}/{source}":
            raise ValueError("untrusted_source")
        if agent.get("source_license") != "MIT" or not re.fullmatch(r"[0-9a-f]{64}", agent.get("source_sha256", "")):
            raise ValueError("unaudited_profile")
        slugs.add(slug)
        paths.add(source)
    return data


def map_marketplace_targets(path: Path = INVENTORY) -> list[dict]:
    """Map to repository catalog/manifests; live org assets require later review.

    No guessed slug becomes a runtime persona. All function overlaps are review
    candidates, and enrichment candidates must not be cloned as new defaults.
    """
    from app.marketplace.seed_catalog import list_catalog_assets

    catalog = {asset.slug: asset for asset in list_catalog_assets()}
    from app.capabilities.agency_enrichment import APPROVED_ENRICHMENTS
    from app.capabilities.paid_media import ROLES

    approved = {spec.source_slug: spec for spec in (*APPROVED_ENRICHMENTS, *ROLES)}
    result = []
    for agent in load_agency_inventory(path)["agents"]:
        department, pack, manifest = DIVISION_TARGETS[agent["division"]]
        source_key = Path(agent["source_path"]).stem
        existing = FUNCTION_TARGETS.get(source_key)
        excluded = agent["proposed_disposition"] == "exclude"
        if excluded:
            pack, manifest, existing = None, None, None
        if pack and (pack not in catalog or catalog[pack].asset_type != "department_pack"):
            raise ValueError("missing_target_pack")
        if existing and (existing not in catalog or catalog[existing].asset_type != "ai_agent"):
            raise ValueError("missing_target_agent")
        result.append({
            "slug": agent["slug"], "department": department,
            "candidate_pack_slug": pack, "candidate_agent_slug": existing,
            "manifest_role": manifest,
            "proposed_disposition": agent["proposed_disposition"],
            "conflict_disposition": (
                "exclude_pending_review" if excluded
                else "review_enrichment" if existing else "review_specialist_scope"
            ),
            "catalog_slug_collision": agent["slug"] in catalog,
            "comparison_scope": "repository_seed_catalog_only",
            "live_catalog_review_required": True,
            "product_approval_required": agent["slug"] not in approved,
            "approval_scope": (
                "new_agent_package" if agent["slug"] in approved and getattr(approved[agent["slug"]], "new_agent", False)
                else "existing_agent_enrichment" if agent["slug"] in approved else None
            ),
        })
    return result


def preview_marketplace_candidates(path: Path = INVENTORY) -> list[CatalogAsset]:
    """Construct review-only catalog previews; never include in list_catalog_assets."""
    data = load_agency_inventory(path)
    mapping = {row["slug"]: row for row in map_marketplace_targets(path)}
    result: list[CatalogAsset] = []
    for agent in data["agents"]:
        if agent["proposed_disposition"] != "marketplace_agent":
            continue
        result.append(CatalogAsset(
            slug=agent["slug"],
            title=agent["name"],
            description=agent["specialty"] or f"{agent['name']} specialist",
            asset_type="ai_agent",
            category="ai_agent",
            department=mapping[agent["slug"]]["department"],
            config={
                "seed_label": f"agent:{agent['slug']}",
                "name": agent["name"],
                "purpose": agent["specialty"] or f"{agent['name']} specialist",
                "role": agent["name"],
                "department": mapping[agent["slug"]]["department"],
                "capabilities": [], "systems": [],
                "guardrails": ["Existing tenant IAM, connector permissions and write approvals remain authoritative."],
                "config": {
                    "source": "agency_agents",
                    "source_revision": data["source_commit"],
                    "source_path": agent["source_path"],
                    "source_sha256": agent["source_sha256"],
                    "source_license": agent["source_license"],
                    "publication_status": "draft_unapproved",
                    "governance_review_required": agent["requires_governance_review"],
                    "marketplaceSlug": agent["slug"],
                    "mapping": mapping[agent["slug"]],
                },
            },
            tags=["agency-agents", agent["division"], "review-only"],
        ))
    return result


def approved_marketplace_candidates() -> list[CatalogAsset]:
    """Return approved enrichments and the three approved Paid Media specialists.

    Product approval for enrichment does not publish or install any asset.
    The remaining source roster stays review-only.
    """
    from app.capabilities.agency_enrichment import APPROVED_ENRICHMENTS
    from app.marketplace.seed_catalog import list_catalog_assets

    from app.capabilities.paid_media import ROLES

    approved = {spec.target_slug for spec in (*APPROVED_ENRICHMENTS, *ROLES)}
    return [asset for asset in list_catalog_assets() if asset.slug in approved]
