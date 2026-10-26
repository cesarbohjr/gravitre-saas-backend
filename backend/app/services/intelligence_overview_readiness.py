"""Evidence-aware connector readiness, without conflating connections with coverage."""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Any


def _fresh(value: Any, *, max_age_hours: int = 72) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    try:
        when = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if when.tzinfo is None:
            return False
        age = (datetime.now(timezone.utc) - when).total_seconds()
        return 0 <= age <= max_age_hours * 3600
    except ValueError:
        return False


def score_readiness(connectors: list[dict[str, Any]]) -> dict[str, Any]:
    """Counts are descriptive, never a proxy for verified analytical sufficiency."""
    usable = [r for r in connectors if r.get("executable")]
    vendors = sorted({str(r.get("vendor") or "").lower() for r in usable if r.get("vendor")})
    fresh = sorted({str(r.get("vendor") or "").lower() for r in usable
                    if r.get("vendor") and _fresh(r.get("last_sync_at"))})
    tier = "insufficient" if not vendors else ("limited" if len(vendors) == 1 else "cross_system_candidate")
    return {
        "tier": tier,
        "connector_count": len(vendors),
        "vendors": vendors,
        "fresh_connectors": fresh,
        "fresh_count": len(fresh),
        "coverage_verified": False,
        "comprehensive": False,
        "recommended_connector_count": 3,
        "missing_evidence": ["authorized_read_scope", "business_function_coverage",
                             "source_record_count", "cross_source_entity_match_quality"],
    }
