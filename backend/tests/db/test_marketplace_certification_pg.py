"""Certifications are service-owned; every publish checks exact persisted config."""
from __future__ import annotations
import os
import pytest
from tests.db.pg_harness import MIGRATIONS, PG_BIN, pg_cluster, requires_pg

if os.environ.get("GRAVITRE_REQUIRE_PG") == "1" and PG_BIN is None:
    pytest.fail("GRAVITRE_REQUIRE_PG=1 but PostgreSQL server binaries are not installed")
pytestmark = requires_pg
MIGRATION = MIGRATIONS / "20261002030000_marketplace_3_certification_evidence.sql"
ORG = "11111111-1111-1111-1111-111111111111"
OTHER = "33333333-3333-3333-3333-333333333333"
ASSET = "22222222-2222-2222-2222-222222222222"
USER = "44444444-4444-4444-4444-444444444444"
BOOTSTRAP_SQL = f"""
CREATE ROLE anon NOLOGIN;
CREATE ROLE authenticated NOLOGIN;
CREATE ROLE service_role NOLOGIN BYPASSRLS;
CREATE SCHEMA auth;
CREATE FUNCTION auth.uid() RETURNS uuid LANGUAGE sql STABLE AS $$
 SELECT nullif(current_setting('request.jwt.claim.sub', true), '')::uuid $$;
GRANT USAGE ON SCHEMA public, auth TO anon, authenticated, service_role;
CREATE TABLE organizations(id uuid PRIMARY KEY);
CREATE TABLE organization_members(org_id uuid, user_id uuid);
CREATE TABLE marketplace_assets(id uuid PRIMARY KEY, org_id uuid, asset_type text, status text, config jsonb);
GRANT SELECT ON organization_members TO authenticated;
GRANT ALL ON marketplace_assets TO service_role;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO authenticated, anon;
INSERT INTO organizations VALUES ('{ORG}'), ('{OTHER}');
INSERT INTO organization_members VALUES ('{ORG}', '{USER}');
INSERT INTO marketplace_assets VALUES ('{ASSET}', '{ORG}', 'outcome_pack', 'draft', '{{"v":1}}');
"""
CERT_SQL = f"""INSERT INTO marketplace_outcome_pack_certifications
(org_id,asset_id,config_digest,config_snapshot,certification_level,publish_ready)
VALUES ('{ORG}','{ASSET}','digest','{{"v":1}}','production_verified',true);"""

@pytest.fixture()
def pg():
    with pg_cluster(BOOTSTRAP_SQL, MIGRATION.read_text()) as db:
        yield db

@pytest.mark.parametrize("role", ["anon", "authenticated"])
def test_user_cannot_write_authoritative_evidence(pg, role):
    assert pg.psql(f"SET ROLE {role}; {CERT_SQL}", check=False).returncode != 0


def test_service_can_certify_and_publish_exact_snapshot(pg):
    pg.psql(f"SET ROLE service_role; {CERT_SQL} UPDATE marketplace_assets SET status='published' WHERE id='{ASSET}';")
    assert pg.psql(f"SELECT status FROM marketplace_assets WHERE id='{ASSET}';").stdout.strip() == "published"


def test_no_certification_and_stale_config_cannot_publish(pg):
    assert pg.psql(f"SET ROLE service_role; UPDATE marketplace_assets SET status='published' WHERE id='{ASSET}';", check=False).returncode != 0
    pg.psql(f"SET ROLE service_role; {CERT_SQL}")
    assert pg.psql(f"SET ROLE service_role; UPDATE marketplace_assets SET config='{{\"v\":2}}',status='published' WHERE id='{ASSET}';", check=False).returncode != 0


def test_member_reads_only_own_evidence(pg):
    pg.psql(f"SET ROLE service_role; {CERT_SQL}")
    assert pg.psql(f"SET ROLE authenticated; SET request.jwt.claim.sub='{USER}'; SELECT count(*) FROM marketplace_outcome_pack_certifications;").stdout.strip() == "1"
    assert pg.psql(f"SET ROLE authenticated; SET request.jwt.claim.sub='{OTHER}'; SELECT count(*) FROM marketplace_outcome_pack_certifications;").stdout.strip() == "0"


def test_config_edit_of_published_asset_cannot_bypass_gate(pg):
    pg.psql(f"SET ROLE service_role; {CERT_SQL} UPDATE marketplace_assets SET status='published' WHERE id='{ASSET}';")
    assert pg.psql(f"SET ROLE service_role; UPDATE marketplace_assets SET config='{{\"v\":2}}' WHERE id='{ASSET}';", check=False).returncode != 0


def test_expired_certification_cannot_publish(pg):
    pg.psql(f"SET ROLE service_role; {CERT_SQL} UPDATE marketplace_outcome_pack_certifications SET expires_at=now()-interval '1 second';")
    assert pg.psql(f"SET ROLE service_role; UPDATE marketplace_assets SET status='published' WHERE id='{ASSET}';", check=False).returncode != 0
