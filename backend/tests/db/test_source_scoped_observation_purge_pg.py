"""Source-scoped removal of customer observations and behaviour signals on disconnect.

Real, throwaway PostgreSQL. Applies the Phase 2B purge migration, the observation
migration and the lineage migration unchanged, then checks that
purge_connector_memories removes only what the disconnected connector fed:
multi-vendor accounts keep their other sources' observations, other orgs are never
touched, a dry run changes nothing, a rerun removes nothing more, and user-confirmed
recipients and channels survive the whole disconnect sequence.
"""
from __future__ import annotations

import json

import pytest

from tests.db.pg_harness import MIGRATIONS, pg_cluster, requires_pg

pytestmark = requires_pg

HARDENING = MIGRATIONS / "20260903120000_memory_hardening_temporal.sql"
PURGE = MIGRATIONS / "20261012024200_source_lifecycle_purge.sql"
OBSERVATIONS = MIGRATIONS / "20261012040000_entity_observations.sql"
LINEAGE = MIGRATIONS / "20261012070000_agent_memory_source_lineage.sql"

ORG = "11111111-1111-4111-8111-111111111111"
OTHER_ORG = "33333333-3333-4333-8333-333333333333"
HS1 = "aaaaaaaa-0000-4000-8000-000000000001"  # hubspot, the one being disconnected
HS2 = "aaaaaaaa-0000-4000-8000-000000000002"  # an earlier hubspot connection of the same org
ZD = "aaaaaaaa-0000-4000-8000-000000000003"  # zendesk, live
GM = "aaaaaaaa-0000-4000-8000-000000000004"  # gmail, live
DISCONNECTED_AT = "2026-10-12 10:00:00+00"

ACME = "cccccccc-0000-4000-8000-000000000001"  # bound to hubspot AND zendesk
GLOBEX = "cccccccc-0000-4000-8000-000000000002"  # bound to zendesk only
FOREIGN = "cccccccc-0000-4000-8000-000000000003"  # other org

O_HS1 = "eeeeeeee-0000-4000-8000-000000000001"  # ACME, hubspot via HS1, before -> removed
O_ZD = "eeeeeeee-0000-4000-8000-000000000002"  # ACME, zendesk via ZD -> kept
O_HS1_AFTER = "eeeeeeee-0000-4000-8000-000000000003"  # ACME, via HS1 after a reconnect -> kept
O_UNTAGGED = "eeeeeeee-0000-4000-8000-000000000004"  # ACME, hubspot, untagged (legacy)
O_HS2 = "eeeeeeee-0000-4000-8000-000000000005"  # ACME, hubspot via HS2 -> kept
O_FOREIGN = "eeeeeeee-0000-4000-8000-000000000006"  # other org, tagged HS1 -> kept
O_GMAIL = "eeeeeeee-0000-4000-8000-000000000007"  # ACME, gmail, untagged -> kept
O_GLOBEX = "eeeeeeee-0000-4000-8000-000000000008"  # GLOBEX, zendesk via ZD -> kept

BOOTSTRAP_SQL = f"""
CREATE ROLE anon NOLOGIN;
CREATE ROLE authenticated NOLOGIN;
CREATE ROLE service_role NOLOGIN BYPASSRLS;
CREATE SCHEMA auth;
CREATE TABLE auth.users (id uuid PRIMARY KEY);
CREATE FUNCTION auth.uid() RETURNS uuid LANGUAGE sql STABLE AS $$ SELECT NULL::uuid $$;
CREATE TABLE public.organizations (id uuid PRIMARY KEY, settings jsonb);
CREATE TABLE public.organization_members (org_id uuid, user_id uuid);
CREATE TABLE public.connectors (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  type text NOT NULL, vendor text, config jsonb NOT NULL DEFAULT '{{}}',
  deleted_at timestamptz
);
CREATE TABLE public.rag_sources (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL, metadata jsonb, created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE public.rag_documents (id uuid PRIMARY KEY, source_id uuid NOT NULL);
CREATE TABLE public.rag_chunks (id uuid PRIMARY KEY, source_id uuid NOT NULL);
CREATE TABLE public.agent_memories (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  agent_id uuid, content text NOT NULL, category text NOT NULL DEFAULT 'fact',
  provenance text, confidence numeric(5, 2) NOT NULL DEFAULT 100,
  is_active boolean NOT NULL DEFAULT true, expires_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE public.org_business_entities (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  canonical_key text NOT NULL DEFAULT ''
);
CREATE TABLE public.org_business_entity_bindings (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL,
  entity_id uuid NOT NULL REFERENCES public.org_business_entities(id) ON DELETE CASCADE,
  system text NOT NULL, resource_type text NOT NULL, resource_id text NOT NULL
);
CREATE TABLE public.org_entity_resolution_records (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL, alias_normalized text NOT NULL, entity_type text NOT NULL DEFAULT '',
  entity_id text NOT NULL DEFAULT '', integration text NOT NULL DEFAULT '',
  source text NOT NULL DEFAULT 'tool_output'
);
GRANT USAGE ON SCHEMA public TO anon, authenticated, service_role;
INSERT INTO public.organizations (id) VALUES ('{ORG}'), ('{OTHER_ORG}');
"""


@pytest.fixture(scope="module")
def pg():
    with pg_cluster(
        BOOTSTRAP_SQL,
        HARDENING.read_text(),
        PURGE.read_text(),
        OBSERVATIONS.read_text(),
        LINEAGE.read_text(),
        "GRANT ALL ON ALL TABLES IN SCHEMA public TO service_role;",
    ) as server:
        yield server


def _obs_row(oid: str, org: str, entity: str, system: str, record: str, connector: str | None, created: str) -> str:
    conn = f"'{connector}'" if connector else "NULL"
    return (
        f"('{oid}', '{org}', '{entity}', 'sentiment', 'negative', -1, 0.9, 'q', '{system}', 'email', "
        f"'{record}', '{created}', 'obs-v1', {conn}, '{created}')"
    )


SEED_SQL = f"""
TRUNCATE public.entity_observations, public.entity_behavior_signals, public.source_purge_receipts,
  public.org_entity_resolution_records, public.org_business_entity_bindings;
DELETE FROM public.org_business_entities;
DELETE FROM public.agent_memories;
DELETE FROM public.connectors;

INSERT INTO public.connectors (id, org_id, type, vendor, deleted_at) VALUES
  ('{HS1}', '{ORG}', 'hubspot', 'hubspot', '{DISCONNECTED_AT}'),
  ('{HS2}', '{ORG}', 'hubspot', 'hubspot', '2026-09-01'),
  ('{ZD}', '{ORG}', 'zendesk', 'zendesk', NULL),
  ('{GM}', '{ORG}', 'gmail', 'gmail', NULL);

INSERT INTO public.org_business_entities (id, org_id, canonical_key) VALUES
  ('{ACME}', '{ORG}', 'acme'), ('{GLOBEX}', '{ORG}', 'globex'), ('{FOREIGN}', '{OTHER_ORG}', 'acme');
INSERT INTO public.org_business_entity_bindings (org_id, entity_id, system, resource_type, resource_id) VALUES
  ('{ORG}', '{ACME}', 'hubspot', 'company', 'hs-1'),
  ('{ORG}', '{ACME}', 'zendesk', 'organization', 'zd-1'),
  ('{ORG}', '{GLOBEX}', 'zendesk', 'organization', 'zd-2'),
  ('{OTHER_ORG}', '{FOREIGN}', 'hubspot', 'company', 'hs-1');

INSERT INTO public.entity_observations (id, org_id, entity_id, dimension, label, score, confidence,
  evidence_quote, source_system, source_record_type, source_record_id, observed_at, extractor_version,
  source_connector_id, created_at) VALUES
  {_obs_row(O_HS1, ORG, ACME, 'hubspot', 'em1', HS1, '2026-10-01')},
  {_obs_row(O_ZD, ORG, ACME, 'zendesk', 'tk1', ZD, '2026-10-01')},
  {_obs_row(O_HS1_AFTER, ORG, ACME, 'hubspot', 'em2', HS1, '2026-10-13')},
  {_obs_row(O_UNTAGGED, ORG, ACME, 'HubSpot', 'em3', None, '2026-09-20')},
  {_obs_row(O_HS2, ORG, ACME, 'hubspot', 'em4', HS2, '2026-08-20')},
  {_obs_row(O_FOREIGN, OTHER_ORG, FOREIGN, 'hubspot', 'em1', HS1, '2026-10-01')},
  {_obs_row(O_GMAIL, ORG, ACME, 'gmail', 'gm1', None, '2026-10-01')},
  {_obs_row(O_GLOBEX, ORG, GLOBEX, 'zendesk', 'tk2', ZD, '2026-10-01')};

INSERT INTO public.entity_behavior_signals (org_id, entity_id, signal, value, baseline, window_end,
  rule_version, evidence_count) VALUES
  ('{ORG}', '{ACME}', 'contact_gap_days', 3, NULL, '2026-10-11', 'beh-v1', 4),
  ('{ORG}', '{ACME}', 'contact_volume_change', 1.5, 2, '2026-10-11', 'beh-v1', 9),
  ('{ORG}', '{GLOBEX}', 'contact_gap_days', 9, NULL, '2026-10-11', 'beh-v1', 3),
  ('{OTHER_ORG}', '{FOREIGN}', 'contact_gap_days', 1, NULL, '2026-10-11', 'beh-v1', 5);

INSERT INTO public.org_entity_resolution_records (org_id, alias_normalized, entity_type, entity_id,
  integration, source) VALUES
  ('{ORG}', 'sarah@acme.com', 'email_recipient', 'sarah@acme.com', 'email', 'parameter_ledger_confirmed'),
  ('{ORG}', '#deals', 'slack_channel', '#deals', 'conversation', 'parameter_ledger_confirmed'),
  ('{ORG}', 'acme', 'company', 'hs-1', 'hubspot', 'tool_output');
"""


@pytest.fixture(autouse=True)
def _seed(pg):
    pg.psql(SEED_SQL)
    yield


def _purge(pg, *, dry_run: bool, org: str = ORG, connector: str = HS1, vendor: str | None = "hubspot") -> dict:
    v = f"'{vendor}'" if vendor else "NULL"
    return json.loads(
        pg.value(
            f"SELECT public.purge_connector_memories('{org}', '{connector}', '{DISCONNECTED_AT}', "
            f"{str(dry_run).lower()}, {v});"
        )
    )


def _derived_purge(pg, *, dry_run: bool) -> dict:
    return json.loads(
        pg.value(
            "SELECT public.purge_connector_derived_data("
            f"'{ORG}', '{HS1}', 'hubspot', '{DISCONNECTED_AT}', {str(dry_run).lower()}, NULL);"
        )
    )


def _obs_ids(pg) -> set[str]:
    return set(filter(None, pg.value("SELECT string_agg(id::text, ',') FROM public.entity_observations;").split(",")))


def _signals(pg) -> set[tuple[str, str]]:
    rows = pg.value("SELECT string_agg(entity_id::text || '/' || signal, ',') FROM public.entity_behavior_signals;")
    return {tuple(r.split("/")) for r in filter(None, rows.split(","))}


def _snapshot(pg) -> str:
    return pg.value(
        "SELECT md5(coalesce((SELECT string_agg(t::text, ',' ORDER BY id) FROM public.entity_observations t), '') "
        "|| coalesce((SELECT string_agg(s::text, ',' ORDER BY id) FROM public.entity_behavior_signals s), '') "
        "|| coalesce((SELECT string_agg(r::text, ',' ORDER BY id) FROM public.org_entity_resolution_records r), ''));"
    )


ALL_OBS = {O_HS1, O_ZD, O_HS1_AFTER, O_UNTAGGED, O_HS2, O_FOREIGN, O_GMAIL, O_GLOBEX}


def test_migration_adds_nullable_observation_lineage_and_is_rerunnable(pg):
    pg.psql(LINEAGE.read_text())
    assert pg.value(
        "SELECT data_type || ':' || is_nullable FROM information_schema.columns "
        "WHERE table_name = 'entity_observations' AND column_name = 'source_connector_id';"
    ) == "uuid:YES"
    assert "WHERE (source_connector_id IS NOT NULL)" in pg.value(
        "SELECT indexdef FROM pg_indexes WHERE indexname = 'idx_entity_observations_org_source_connector';"
    )


def test_multi_vendor_account_loses_only_the_purged_sources_observations(pg):
    counts = _purge(pg, dry_run=False)
    assert counts["entity_observations"] == 2
    assert counts["entity_observations_unattributed"] == 0
    assert counts["entity_behavior_signals"] == 2
    # HS1's row before the disconnect, and the untagged HubSpot row (no other live
    # HubSpot connection could own it). Zendesk, Gmail, the other HubSpot connection,
    # the reconnect and the other org keep theirs.
    assert _obs_ids(pg) == ALL_OBS - {O_HS1, O_UNTAGGED}
    # The account itself stays (it is still bound to Zendesk); its signals, built on
    # the removed rows too, are dropped for the daily rule run to rebuild.
    assert pg.value(f"SELECT count(*) FROM public.org_business_entities WHERE id = '{ACME}';") == "1"
    assert _signals(pg) == {(GLOBEX, "contact_gap_days"), (FOREIGN, "contact_gap_days")}


def test_untagged_rows_are_kept_and_reported_when_another_connection_of_the_vendor_is_live(pg):
    pg.psql(f"UPDATE public.connectors SET deleted_at = NULL WHERE id = '{HS2}';")
    counts = _purge(pg, dry_run=False)
    assert counts["entity_observations"] == 1
    assert counts["entity_observations_unattributed"] == 1
    assert _obs_ids(pg) == ALL_OBS - {O_HS1}


def test_untagged_rows_are_kept_when_the_connector_itself_is_live_again(pg):
    pg.psql(f"UPDATE public.connectors SET deleted_at = NULL WHERE id = '{HS1}';")
    counts = _purge(pg, dry_run=False)
    assert counts["entity_observations"] == 1 and counts["entity_observations_unattributed"] == 1
    assert O_UNTAGGED in _obs_ids(pg) and O_HS1 not in _obs_ids(pg)


def test_vendor_comes_from_the_connector_row_when_not_given(pg):
    assert _purge(pg, dry_run=False, vendor=None)["entity_observations"] == 2
    assert _obs_ids(pg) == ALL_OBS - {O_HS1, O_UNTAGGED}


def test_other_orgs_are_never_touched(pg):
    foreign_before = pg.value(
        f"SELECT md5(string_agg(t::text, ',' ORDER BY id)) FROM public.entity_observations t WHERE org_id = '{OTHER_ORG}';"
    )
    _purge(pg, dry_run=False)
    assert pg.value(
        f"SELECT md5(string_agg(t::text, ',' ORDER BY id)) FROM public.entity_observations t WHERE org_id = '{OTHER_ORG}';"
    ) == foreign_before
    assert (FOREIGN, "contact_gap_days") in _signals(pg)
    # And a purge for the other org removes only its own row.
    assert _purge(pg, dry_run=False, org=OTHER_ORG)["entity_observations"] == 1
    assert _obs_ids(pg) == ALL_OBS - {O_HS1, O_UNTAGGED, O_FOREIGN}


def test_dry_run_changes_nothing_and_records_the_plan(pg):
    _derived_purge(pg, dry_run=True)
    before = _snapshot(pg)
    counts = _purge(pg, dry_run=True)
    assert counts["entity_observations"] == 2 and counts["entity_behavior_signals"] == 2
    assert counts["receipt_merged"] is True
    assert _snapshot(pg) == before
    receipt = json.loads(pg.value("SELECT counts FROM public.source_purge_receipts WHERE dry_run;"))
    assert receipt["entity_observations"] == 2 and receipt["entity_behavior_signals"] == 2
    assert receipt["entity_observations_unattributed"] == 0


def test_rerun_removes_nothing_more_and_keeps_the_first_receipt(pg):
    _derived_purge(pg, dry_run=False)
    first = _purge(pg, dry_run=False)
    after_first = _snapshot(pg)
    second = _purge(pg, dry_run=False)
    assert first["entity_observations"] == 2 and first["receipt_merged"] is True
    assert second["entity_observations"] == 0 and second["entity_behavior_signals"] == 0
    assert second["receipt_merged"] is False
    assert _snapshot(pg) == after_first
    receipt = json.loads(pg.value("SELECT counts FROM public.source_purge_receipts WHERE NOT dry_run;"))
    assert receipt["entity_observations"] == 2


def test_full_disconnect_keeps_user_confirmed_recipients_and_channels(pg):
    # The handler's order: derived data first, then memories and observations.
    derived = _derived_purge(pg, dry_run=False)
    assert derived["vendor_shared"] is False and derived["entity_aliases"] == 1
    _purge(pg, dry_run=False)
    kept = pg.value(
        "SELECT string_agg(integration || ':' || alias_normalized, ',' ORDER BY integration) "
        f"FROM public.org_entity_resolution_records WHERE org_id = '{ORG}';"
    )
    assert kept == "conversation:#deals,email:sarah@acme.com"
    # The multi-vendor account survives the vendor-binding purge, without HubSpot's observations.
    assert pg.value(f"SELECT count(*) FROM public.org_business_entity_bindings WHERE entity_id = '{ACME}';") == "1"
    assert _obs_ids(pg) == ALL_OBS - {O_HS1, O_UNTAGGED}


def test_agent_memories_from_other_sources_are_untouched_alongside(pg):
    pg.psql(
        "INSERT INTO public.agent_memories (org_id, content, source_connector_id, created_at) VALUES "
        f"('{ORG}', 'from hubspot', '{HS1}', '2026-10-01'), ('{ORG}', 'from zendesk', '{ZD}', '2026-10-01'), "
        f"('{ORG}', 'user said', NULL, '2026-10-01');"
    )
    counts = _purge(pg, dry_run=False)
    assert counts["agent_memories"] == 1
    assert pg.value("SELECT string_agg(content, ',' ORDER BY content) FROM public.agent_memories;") == (
        "from zendesk,user said"
    )
