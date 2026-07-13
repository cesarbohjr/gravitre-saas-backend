#!/usr/bin/env python3
"""CRM outcome emit evidence — unit wiring verified; live HubSpot webhook optional.

Writes docs/delivery/crm-outcome-emit-live.json
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

from dotenv import dotenv_values
from supabase import create_client

REPO = Path(__file__).resolve().parent.parent
BACKEND = REPO / "backend"
sys.path.insert(0, str(BACKEND))

ORG = "cbbf993b-b22f-41ce-964b-1fc25e0dd9ea"
OUT = REPO / "docs" / "delivery" / "crm-outcome-emit-live.json"


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_env() -> None:
    merged: dict[str, str] = {}
    for p in (BACKEND / ".env", BACKEND / ".env.operator.local", REPO / ".env"):
        if p.is_file():
            try:
                merged.update({k: v for k, v in dotenv_values(p).items() if v})
            except UnicodeDecodeError:
                pass
    for k, v in merged.items():
        os.environ.setdefault(k, v)


def main() -> int:
    _load_env()
    from app.services.crm_outcome_capture_service import count_crm_outcomes
    from app.services.hubspot_trigger_service import (
        map_hubspot_event_to_crm_outcome,
        maybe_emit_crm_outcome_from_hubspot_event,
    )

    # Unit-level mapping proof (always)
    event = {
        "subscriptionType": "deal.propertyChange",
        "propertyName": "dealstage",
        "propertyValue": "closedwon",
        "objectId": "smoke-deal-phase3",
        "portalId": 0,
    }
    mapped = map_hubspot_event_to_crm_outcome(event, {"deal": {"id": "smoke-deal-phase3"}})
    mapping_ok = mapped == {"outcome_type": "won", "external_record_id": "smoke-deal-phase3"}

    client = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"])
    before = count_crm_outcomes(client, ORG)

    # Synthetic emit into prod smoke org (real insert — explicit closedwon only)
    emit = maybe_emit_crm_outcome_from_hubspot_event(
        client,
        org_id=ORG,
        event=event,
        normalized={"deal": {"id": "smoke-deal-phase3"}},
    )
    after = count_crm_outcomes(client, ORG)

    # Soft-dedupe second call
    emit2 = maybe_emit_crm_outcome_from_hubspot_event(
        client,
        org_id=ORG,
        event=event,
        normalized={"deal": {"id": "smoke-deal-phase3"}},
    )

    passed = (
        mapping_ok
        and bool(emit)
        and emit.get("outcomeType") == "won"
        and after >= before
        and bool(emit2)
        and (emit2.get("deduped") is True or emit2.get("id") == emit.get("id"))
    )

    artifact = {
        "pass": passed,
        "ran_at": utcnow(),
        "org_id": ORG,
        "mode": "synthetic_hubspot_closedwon_emit",
        "mapping_ok": mapping_ok,
        "count_before": before,
        "count_after": after,
        "emit": emit,
        "emit_dedupe": emit2,
        "phase_5_ml": "HELD",
        "note": (
            "First production caller wired in hubspot_trigger_service. "
            "This artifact uses a synthetic closedwon event against the smoke org "
            "(explicit label only). Real HubSpot webhook traffic will use the same path. "
            "Phase 5 ML remains HELD."
        ),
        "waiting_on_real_hubspot_webhook": True,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"pass": passed, "out": str(OUT), "count_before": before, "count_after": after}, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
