"""Deterministic, read-only release review for all pinned Agency Agents roles.

Never interprets a proposal as publication authorization.
"""
from __future__ import annotations

from collections import Counter
from typing import Any

from app.marketplace.agency_agents_catalog import load_agency_inventory, map_marketplace_targets


def build_release_review() -> dict[str, Any]:
    inventory = load_agency_inventory()
    targets = {item["slug"]: item for item in map_marketplace_targets()}
    roles = []
    for profile in inventory["agents"]:
        target = targets[profile["slug"]]
        if target["proposed_disposition"] == "exclude":
            status = "excluded_pending_review"
        elif target["product_approval_required"]:
            status = "awaiting_product_approval"
        elif target["live_catalog_review_required"]:
            status = "approved_scope_live_review_pending"
        else:
            status = "review_pending"
        roles.append({
            "slug": profile["slug"],
            "division": profile["division"],
            "source_commit": inventory["source_commit"],
            "source_sha256": profile["source_sha256"],
            "target_agent": target["candidate_agent_slug"],
            "target_pack": target["candidate_pack_slug"],
            "disposition": target["proposed_disposition"],
            "approval_scope": target["approval_scope"],
            "review_status": status,
            "deployment_status": "not_verified",
            "certification_status": "not_run",
            "requires_governance_review": profile["requires_governance_review"],
            "live_catalog_review_required": target["live_catalog_review_required"],
        })
    counts = Counter(item["review_status"] for item in roles)
    return {
        "schema_version": 1,
        "source_commit": inventory["source_commit"],
        "profile_count": len(roles),
        "division_count": len(inventory["divisions"]),
        "review_status_counts": dict(sorted(counts.items())),
        "production_publication_authorized": False,
        "roles": roles,
    }
