"""Evidence-grounded recommendations generated only from persisted tenant observations.

No monetary impact, causality, provider writes, or Play execution is inferred.
"""
from __future__ import annotations
import hashlib
from typing import Any

def build_evidence_recommendations(records: list[dict[str, Any]], matches: list[dict[str, Any]], *, org_id: str) -> list[dict[str, Any]]:
    owned = {(str(r["connector_id"]), str(r["object_type"]), str(r["external_id"]))
             for r in records if r.get("org_id") == org_id}
    output = []
    for match in matches:
        if match.get("org_id") != org_id or match.get("match_status") not in {"verified_key", "candidate"}:
            continue
        refs = match.get("record_references") or []
        keys = {(str(r.get("connector_id")), str(r.get("object_type")), str(r.get("external_id"))) for r in refs if isinstance(r, dict)}
        if len(keys) < 2 or not keys.issubset(owned):
            continue
        if len({key[0] for key in keys}) < 2:
            continue
        digest = str(match.get("identity_hash") or "")
        if len(digest) != 64:
            continue
        verified = match["match_status"] == "verified_key"
        output.append({
            "id": "identity-review:" + hashlib.sha256((org_id + ":" + digest).encode()).hexdigest()[:24],
            "kind": "cross_provider_identity_review",
            "title": "Review cross-system customer records",
            "description": "Records from multiple connected systems share an exact identity key; review before taking action.",
            "finding": {"shared_identity_kind": match["identity_kind"],
                        "record_count": len(keys), "evidence_strength": "exact_key" if verified else "candidate"},
            "sources": [{"connector_id": a, "object_type": b, "external_id": c}
                        for a, b, c in sorted(keys)],
            "recommended_play_key": "customer-rescue",
            "business_impact": None,
            "causal_claim": False,
            "advisory_only": True,
            "approval_required": True,
            "outcome_verified": False,
        })
    return sorted(output, key=lambda row: row["id"])[:100]
