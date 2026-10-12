"""Phase 3 observation tables and behavioural SQL rules against real PostgreSQL."""
from __future__ import annotations

import json

import pytest

from tests.db.pg_harness import MIGRATIONS, pg_cluster, requires_pg

pytestmark = requires_pg

MIGRATION = MIGRATIONS / "20261012040000_entity_observations.sql"
ORG = "11111111-1111-4111-8111-111111111111"
MEMBER = "22222222-2222-4222-8222-222222222222"
ACME = "cccccccc-0000-4000-8000-000000000001"
GLOBEX = "cccccccc-0000-4000-8000-000000000002"
AS_OF = "2026-10-12 12:00:00+00"

BOOTSTRAP_SQL = f"""
CREATE ROLE anon NOLOGIN;
CREATE ROLE authenticated NOLOGIN;
CREATE ROLE service_role NOLOGIN BYPASSRLS;
CREATE SCHEMA auth;
CREATE TABLE auth.users (id uuid PRIMARY KEY);
CREATE FUNCTION auth.uid() RETURNS uuid LANGUAGE sql STABLE AS $$
  SELECT nullif(current_setting('request.jwt.claim.sub', true), '')::uuid $$;
CREATE TABLE public.organizations (id uuid PRIMARY KEY);
CREATE TABLE public.organization_members (org_id uuid, user_id uuid);
CREATE TABLE public.org_business_entities (
  id uuid PRIMARY KEY, org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE
);
GRANT USAGE ON SCHEMA public, auth TO anon, authenticated, service_role;
GRANT SELECT ON public.organization_members TO authenticated;
INSERT INTO public.organizations VALUES ('{ORG}');
INSERT INTO auth.users VALUES ('{MEMBER}');
INSERT INTO public.organization_members VALUES ('{ORG}', '{MEMBER}');
INSERT INTO public.org_business_entities VALUES ('{ACME}', '{ORG}'), ('{GLOBEX}', '{ORG}');
"""


@pytest.fixture(scope="module")
def pg():
    with pg_cluster(BOOTSTRAP_SQL, MIGRATION.read_text()) as server:
        yield server


@pytest.fixture(autouse=True)
def _clean(pg):
    pg.psql("TRUNCATE public.entity_observations, public.entity_behavior_signals;")
    yield


def _obs(pg, entity: str, days_ago: float, record: str, dim: str = "sentiment", status: str = "active") -> None:
    pg.psql(
        "INSERT INTO public.entity_observations (org_id, entity_id, dimension, label, score, confidence,"
        " evidence_quote, source_system, source_record_type, source_record_id, observed_at, extractor_version, status)"
        f" VALUES ('{ORG}', '{entity}', '{dim}', 'neutral', 0, 0.9, 'q', 'hubspot', 'email', '{record}',"
        f" timestamptz '{AS_OF}' - interval '{days_ago} days', 'obs-v1', '{status}');"
    )


def _signals(pg) -> dict[tuple[str, str], dict]:
    rows = json.loads(pg.value("SELECT coalesce(json_agg(s), '[]') FROM public.entity_behavior_signals s;"))
    return {(r["entity_id"], r["signal"]): r for r in rows}


def test_migration_is_idempotent(pg):
    pg.psql(MIGRATION.read_text())


def test_one_observation_per_record_dimension_and_version(pg):
    _obs(pg, ACME, 1, "e1")
    res = pg.psql(
        "INSERT INTO public.entity_observations (org_id, entity_id, dimension, label, score, confidence,"
        " evidence_quote, source_system, source_record_type, source_record_id, observed_at, extractor_version)"
        f" VALUES ('{ORG}', '{ACME}', 'sentiment', 'neutral', 0, 0.9, 'q', 'hubspot', 'email', 'e1', now(), 'obs-v1');",
        check=False,
    )
    assert res.returncode != 0 and "entity_observations_once" in res.stderr


@pytest.mark.parametrize(
    "bad",
    ["dimension => 'employee_mood'", "score => 2", "confidence => 1.5", "evidence_quote => ''"],
)
def test_constraints_reject_bad_rows(pg, bad):
    col, val = (p.strip() for p in bad.split("=>"))
    values = {
        "dimension": "'sentiment'", "score": "0", "confidence": "0.9", "evidence_quote": "'q'",
    }
    values[col] = val
    res = pg.psql(
        "INSERT INTO public.entity_observations (org_id, entity_id, dimension, label, score, confidence,"
        " evidence_quote, source_system, source_record_type, source_record_id, observed_at, extractor_version)"
        f" VALUES ('{ORG}', '{ACME}', {values['dimension']}, 'x', {values['score']}, {values['confidence']},"
        f" {values['evidence_quote']}, 'hubspot', 'email', 'z', now(), 'obs-v1');",
        check=False,
    )
    assert res.returncode != 0


def test_behaviour_rules_count_distinct_messages_and_need_a_baseline(pg):
    # ACME: 6 messages in the last 14 days, 4 in the 56 days before (baseline 1 per 14 days).
    for i in range(6):
        _obs(pg, ACME, 1 + i, f"r{i}")
        _obs(pg, ACME, 1 + i, f"r{i}", dim="urgency")  # same message, second dimension: not a new contact
    for i in range(4):
        _obs(pg, ACME, 20 + i * 10, f"p{i}")
    _obs(pg, ACME, 2, "gone", status="retracted")
    # GLOBEX: 3 messages, all old; no baseline for volume, but a gap.
    for i in range(3):
        _obs(pg, GLOBEX, 40 + i, f"g{i}")
    written = pg.value(f"SELECT public.compute_entity_behavior_signals('{ORG}', '{AS_OF}');")
    assert written == "3"
    s = _signals(pg)
    vol = s[(ACME, "contact_volume_change")]
    assert vol["value"] == 6.0 and vol["baseline"] == 1.0 and vol["evidence_count"] == 10
    assert (GLOBEX, "contact_volume_change") not in s
    assert round(s[(GLOBEX, "contact_gap_days")]["value"]) == 40
    assert round(s[(ACME, "contact_gap_days")]["value"]) == 1
    # Re-running on the same day updates in place.
    assert pg.value(f"SELECT public.compute_entity_behavior_signals('{ORG}', '{AS_OF}');") == "3"
    assert pg.value("SELECT count(*) FROM public.entity_behavior_signals;") == "3"


def test_entity_deletion_removes_its_observations_and_signals(pg):
    for i in range(3):
        _obs(pg, GLOBEX, 1 + i, f"g{i}")
    pg.value(f"SELECT public.compute_entity_behavior_signals('{ORG}', '{AS_OF}');")
    pg.psql(f"DELETE FROM public.org_business_entities WHERE id = '{GLOBEX}';")
    assert pg.value(f"SELECT count(*) FROM public.entity_observations WHERE entity_id = '{GLOBEX}';") == "0"
    assert pg.value(f"SELECT count(*) FROM public.entity_behavior_signals WHERE entity_id = '{GLOBEX}';") == "0"
    pg.psql(f"INSERT INTO public.org_business_entities VALUES ('{GLOBEX}', '{ORG}');")


def test_members_read_only_and_rpc_is_service_only(pg):
    _obs(pg, ACME, 1, "e1")
    read = pg.value(
        f"SET ROLE authenticated; SET request.jwt.claim.sub = '{MEMBER}';"
        " SELECT count(*) FROM public.entity_observations;"
    )
    assert read == "1"
    outsider = pg.value(
        "SET ROLE authenticated; SET request.jwt.claim.sub = '99999999-9999-4999-8999-999999999999';"
        " SELECT count(*) FROM public.entity_observations;"
    )
    assert outsider == "0"
    res = pg.psql(
        f"SET ROLE authenticated; SET request.jwt.claim.sub = '{MEMBER}';"
        " UPDATE public.entity_observations SET label = 'positive';",
        check=False,
    )
    assert res.returncode != 0 and "permission denied" in res.stderr
    res = pg.psql(
        f"SET ROLE authenticated; SELECT public.compute_entity_behavior_signals('{ORG}', now());", check=False
    )
    assert res.returncode != 0 and "permission denied" in res.stderr
