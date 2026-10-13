"""The legacy lineage audit is read-only and classifies every memory into one group.

Runs docs/delivery/memory-lineage-legacy-audit-2026-10-12.sql against a real,
throwaway PostgreSQL inside BEGIN READ ONLY (any write would fail the transaction),
then checks the group counts and that nothing changed.
"""
from __future__ import annotations

import re

import pytest

from tests.db.pg_harness import REPO_ROOT, pg_cluster, requires_pg
from tests.db.test_source_scoped_observation_purge_pg import (
    BOOTSTRAP_SQL,
    HARDENING,
    LINEAGE,
    OBSERVATIONS,
    ORG,
    OTHER_ORG,
    PURGE,
)

pytestmark = requires_pg

AUDIT = REPO_ROOT / "docs" / "delivery" / "memory-lineage-legacy-audit-2026-10-12.sql"

SEED_SQL = f"""
INSERT INTO public.connectors (org_id, type, vendor) VALUES ('{ORG}', 'hubspot', 'hubspot');
INSERT INTO public.connectors (org_id, type, vendor, deleted_at) VALUES ('{ORG}', 'zendesk', 'zendesk', now());
INSERT INTO public.agent_memories (org_id, content, provenance, source_class, is_active) VALUES
  ('{ORG}', 'probe', 'one_brain_workspace_memory_probe', 'probe', true),
  ('{ORG}', 'Confirmed action: send email', 'connector_confirm:conversation:c1', 'model_inference', true),
  ('{ORG}', 'Confirmed action: create deal', 'connector_confirm', NULL, false),
  ('{OTHER_ORG}', 'Their CFO prefers quarterly billing', 'untrusted_external', 'untrusted_external', true),
  ('{ORG}', 'Workflow w1 outcome=completed', 'outcome_learning', 'workflow_outcome', true),
  ('{ORG}', 'Outcome workflow_executed', 'learn_outcome:workflow_executed', 'workflow_outcome', true),
  ('{ORG}', 'Glossary: ARR', 'v4:auto:glossary', NULL, true),
  ('{ORG}', 'ICP is 50-200', 'user_statement', 'user_direct', true),
  ('{ORG}', 'They prefer email', 'model_extracted_turn', 'model_inference', true),
  ('{ORG}', 'Zendesk ticket 88: renewal at risk', 'model_extracted_turn', 'model_inference', true),
  ('{ORG}', 'Old fact', NULL, NULL, true);
"""


@pytest.fixture(scope="module")
def pg():
    with pg_cluster(
        BOOTSTRAP_SQL,
        HARDENING.read_text(),
        PURGE.read_text(),
        OBSERVATIONS.read_text(),
        LINEAGE.read_text(),
        SEED_SQL,
    ) as server:
        yield server


def _without_comments(sql: str) -> str:
    return "\n".join(line.split("--", 1)[0] for line in sql.splitlines())


def test_audit_has_no_writes():
    body = _without_comments(AUDIT.read_text()).upper()
    for verb in ("INSERT", "UPDATE", "DELETE", "TRUNCATE", "ALTER", "DROP", "CREATE", "GRANT", "REVOKE"):
        assert not re.search(rf"\b{verb}\b", body), verb


def test_audit_runs_read_only_and_classifies_every_memory(pg):
    snapshot = "SELECT md5(string_agg(t::text, ',' ORDER BY id)) FROM public.agent_memories t;"
    before = pg.value(snapshot)
    out = pg.psql("BEGIN READ ONLY;\n" + AUDIT.read_text() + "\nROLLBACK;").stdout
    assert pg.value(snapshot) == before
    groups = {}
    for line in out.splitlines():
        cols = line.split("|")
        if re.match(r"^G\d ", cols[0]):
            groups[cols[0]] = (int(cols[1]), int(cols[2]))  # rows, active
    assert groups == {
        "G1 probe": (1, 1),
        "G2 connector_confirm": (2, 1),
        "G3 external_content": (1, 1),
        "G4 outcome": (2, 2),
        "G5 promotion_v4": (1, 1),
        "G6 user_direct": (1, 1),
        "G7 model_inference": (2, 2),
        "G8 unclassified": (1, 1),
    }
    assert sum(r for r, _a in groups.values()) == int(pg.value("SELECT count(*) FROM public.agent_memories;"))
    # Query 1: all three lineage columns are present after the migration.
    assert out.splitlines()[0] == "3"
    # Query 3: the per-org breakdown of possible connector content.
    assert f"{ORG}|2|0|1" in out and f"{OTHER_ORG}|0|1|1" in out


def test_audit_points_at_untagged_memories_naming_a_revoked_vendor(pg):
    """Queries 6 and 7: likely origin by vendor, and which vendors are no longer live."""
    out = pg.psql("BEGIN READ ONLY;\n" + AUDIT.read_text() + "\nROLLBACK;").stdout
    origin = sorted(
        tuple(line.split("|")[1:7]) for line in out.splitlines() if line.startswith("origin|")
    )
    assert origin == [
        ("G2 connector_confirm", "-", "no_vendor_named", "2", "1", "1"),
        ("G3 external_content", "-", "no_vendor_named", "1", "1", "1"),
        ("G7 model_inference", "-", "no_vendor_named", "1", "1", "1"),
        ("G7 model_inference", "zendesk", "revoked_vendor", "1", "1", "1"),
        ("G8 unclassified", "-", "no_vendor_named", "1", "1", "1"),
    ]
    zendesk_id = pg.value("SELECT id FROM public.agent_memories WHERE content LIKE 'Zendesk%';")
    sample = [line for line in out.splitlines() if line.startswith("revoked_sample|")]
    assert sample == [f"revoked_sample|{ORG}|zendesk|1|{{{zendesk_id}}}"]
