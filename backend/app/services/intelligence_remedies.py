"""Evidence-linked next steps within Gravitre. Suggestions never execute work."""
from __future__ import annotations

from typing import Any
from urllib.parse import urlencode


def remedies_for_recommendation(item: dict[str, Any]) -> list[dict[str, str]]:
    from app.plays.catalog import get_platform_play

    kind = item.get("kind")
    dims = {str(d.get("key")) for d in item.get("dimensions") or [] if isinstance(d, dict)}
    dim = str(item.get("dimension") or "")
    if dim:
        dims.add(dim)
    play = str(item.get("playKey") or "")
    if not play and kind in {"account_health", "account_change"}:
        if dims & {"sentiment", "churn_risk_language", "support_friction"}:
            play = "customer-rescue"
        elif dims & {"contact_gap", "contact_volume"}:
            play = "client-risk-radar"
        elif any(r.get("source") == "churn_model" and r.get("reading") in {"high", "medium"}
                 for r in item.get("readings") or [] if isinstance(r, dict)):
            play = "customer-rescue"
    definition = get_platform_play(play) if play else None
    if definition:
        return [{
            "label": f"Review {definition.name}",
            "href": f"/plays/{definition.key}",
            "why": "Review the account evidence and Play readiness before starting. Actions keep their normal approval gates.",
        }]
    # A bespoke review is useful even when no existing Play fits. Carry the
    # evidence into the real assignment composer, never an external tracker.
    if kind in {"account_health", "account_change", "business_signal"} and item.get("evidence"):
        brief = (
            f"Review this intelligence finding: {item.get('title') or 'Business signal'}.\n"
            f"Basis: {item.get('why') or ''}\nEvidence:\n"
            + "\n".join(str(e) for e in item["evidence"][:5])
            + "\nRecommend a Gravitre Play or workflow if the evidence supports it. Prepare a review only; do not contact customers or change connected systems."
        )
        return [{"label": "Prepare review assignment", "href": "/assignments/new?" + urlencode({"task": brief}),
                 "why": "Review the brief and choose an agent before starting. This suggestion has not created or run anything."}]
    return []
