"""Seed one real, clearly-labeled fixture work_object + external_signal row
for the "[FIXTURE] Phase 4 Evidence Graph Verification" organization, so the
WhyGravitrePanel evidence graph has a real, non-mocked, non-"missing" evidence
contribution to visually verify against, per the explicit user instruction:

  "Create a fresh, purpose-named org for Phase 4 evidence-graph verification
  (do not reuse Phase4 Deploy Verify), seed it with real, labeled fixture
  data, and capture live, visual confirmation of the populated
  WhyGravitrePanel."

Why this specific recipe:
  `DepartmentSignalScoringService._resolve_source_status()` resolves the
  `sales.census_kf` source (which feeds the `sales.firmographic_fit` signal,
  weight=0.20) to status "knowledge_fabric_only" purely from a static,
  global registry check (no `connector_vendor` set on that source), which is
  independent of any org's actually-connected integrations. So a single
  `external_signals` row with vendor="census" plus a single `work_objects`
  row (department=sales, object_type=opportunity, status != archived) is
  sufficient to make the evidence graph show a real, populated,
  non-"missing" contribution without needing any live OAuth connector setup.

Disclosure (no-invented-customer-surfaces rule): this fixture data is
(a) explicitly requested and authorized in this conversation as verification
scaffolding for the Phase 4 evidence-graph feature, not a real customer
price/claim/badge. Both rows carry an unmistakable "[FIXTURE]" label in their
user-visible title so nobody could mistake them for real product data if a
human ever opened this org's data directly.

Usage:
    python backend/scripts/seed_phase4_evidence_fixture.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.stdout.reconfigure(encoding="utf-8")

from probe_classical_region_reach import load_env  # noqa: E402

from supabase import create_client  # noqa: E402

FIXTURE_ORG_NAME = "[FIXTURE] Phase 4 Evidence Graph Verification"
FIXTURE_ORG_SLUG = "fixture-phase-4-evidence-graph-verification"


def main() -> int:
    env = load_env()
    sb = create_client(env["SUPABASE_URL"], env["SUPABASE_SERVICE_ROLE_KEY"])

    org_rows = (
        sb.table("organizations")
        .select("id,name")
        .eq("name", FIXTURE_ORG_NAME)
        .limit(5)
        .execute()
        .data
        or []
    )
    if not org_rows:
        print(f"ERROR: no organization found with name={FIXTURE_ORG_NAME!r}")
        return 1
    if len(org_rows) > 1:
        print(f"ERROR: expected exactly one org named {FIXTURE_ORG_NAME!r}, found {len(org_rows)}: {org_rows}")
        return 1
    org_id = org_rows[0]["id"]
    print(f"Found fixture org id={org_id} name={org_rows[0]['name']!r}")

    # Idempotency: don't double-seed if this script is re-run.
    existing_wo = (
        sb.table("work_objects")
        .select("id,title")
        .eq("org_id", org_id)
        .like("title", "[FIXTURE]%")
        .execute()
        .data
        or []
    )
    if existing_wo:
        print(f"work_objects already seeded: {existing_wo}")
    else:
        wo_payload = {
            "org_id": org_id,
            "object_type": "opportunity",
            "department": "sales",
            "title": "[FIXTURE] Acme Test Corp — Phase 4 evidence verification opportunity",
            "objective": "Non-real fixture opportunity created solely to verify the Phase 4 "
            "WhyGravitrePanel evidence graph renders real (non-mocked) evidence rows. "
            "Not a real customer or deal.",
            "status": "identified",
            "priority": "medium",
        }
        wo_result = sb.table("work_objects").insert(wo_payload).execute()
        wo_rows = wo_result.data or []
        print(f"Inserted work_objects row: {wo_rows}")

    existing_es = (
        sb.table("external_signals")
        .select("id,title")
        .eq("org_id", org_id)
        .like("title", "[FIXTURE]%")
        .execute()
        .data
        or []
    )
    if existing_es:
        print(f"external_signals already seeded: {existing_es}")
    else:
        es_payload = {
            "org_id": org_id,
            "signal_definition_id": "sales.census_kf",
            "vendor": "census",
            "signal_type": "business_formation",
            "title": "[FIXTURE] Census business-formation signal — Phase 4 evidence verification",
            "severity": "info",
            "payload": {
                "note": "Non-real fixture signal created solely to verify the Phase 4 "
                "WhyGravitrePanel evidence graph renders real (non-mocked) evidence rows. "
                "Not real Census Bureau data.",
                "fixture": True,
            },
            "provenance": {"source": "manual_fixture_seed", "fixture": True},
        }
        es_result = sb.table("external_signals").insert(es_payload).execute()
        es_rows = es_result.data or []
        print(f"Inserted external_signals row: {es_rows}")

    print("\nDone. org_id =", org_id)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
