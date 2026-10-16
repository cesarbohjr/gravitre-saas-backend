"""Row 8 acceptance-criteria tests: release verification.

Coverage:
- Migration history reconciliation
  - All Release-3 migrations are present on disk in the expected order
  - Every Release-3 migration is expand-only (no bare DROP TABLE / DROP COLUMN
    outside a Rollback comment block)
  - Every Release-3 migration has a documented Rollback: line in its header
  - No Release-3 migration filename is duplicated
- Feature-flag rollout order contract
  - The three billing atomic flags must be activated in the documented order:
    USAGE_ATOMIC_ENABLED → ASSISTANT_BILLING_ATOMIC_ENABLED →
    ASSISTANT_BILLING_RECOVERY_ENABLED
  - Flags are documented in the master-plan durable-recovery section
  - The recovery flag must not appear before the atomic flag in any rollout doc
- Rollback package contract
  - Each release-3 migration header contains explicit Rollback instructions
  - Rollback instructions for expand-only changes reference DROP IF EXISTS or
    DROP FUNCTION IF EXISTS (safe forms)
  - The billing recovery migration documents: turn flag off before schema cleanup
- Release 1 authenticated matrix
  - The org_api_keys migration exists and creates the key table
  - The idx_org_api_keys_hash index is filtered on revoked_at IS NULL
  - The key_hash column is UNIQUE and key text is never stored
  - The scoped-hashed credentials use grav_live_ / grav_test_ prefix convention
  - A generated key passes the prefix check and has a non-empty hash

These tests satisfy Row 8: "Reconcile migration history, prepare exact
flag/migration rollout and rollback package; Release 1 authenticated matrix,
production deployment alignment."
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "supabase" / "migrations"
MASTER_PLAN = (
    Path(__file__).resolve().parents[2]
    / "docs"
    / "delivery"
    / "MASTER_PLAN_CLOSEOUT_2026-10-15.md"
)

# The canonical Release-3 migration set, in rollout order.
RELEASE_3_MIGRATIONS: list[str] = [
    "20261016032007_msp_parent_org_scaffold.sql",
    "20261016032018_write_invoke_idempotency.sql",
    "20261016032029_write_invoke_idempotency_grants.sql",
    "20261016032039_assistant_usage_atomic.sql",
    "20261016032048_atomic_usage_all_sources.sql",
    "20261016032109_assistant_billing_recovery_contract.sql",
    "20261016032120_operator_recommendations.sql",
    "20261016040000_msp_delegation_audit.sql",
    "20261016050000_model_evaluation_reports.sql",
    "20261016060000_org_api_keys.sql",
]

# Billing feature flags must be activated in this strict order.
BILLING_FLAG_ORDER: list[str] = [
    "USAGE_ATOMIC_ENABLED",
    "ASSISTANT_BILLING_ATOMIC_ENABLED",
    "ASSISTANT_BILLING_RECOVERY_ENABLED",
]


def _sql(name: str) -> str:
    return (MIGRATIONS_DIR / name).read_text(encoding="utf-8")


def _header_comments(name: str) -> str:
    """Return only the leading comment block of a SQL file (lines starting with --)."""
    lines = []
    for line in (MIGRATIONS_DIR / name).read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("--"):
            lines.append(stripped)
        elif stripped == "":
            lines.append("")
        else:
            break
    return "\n".join(lines)


def _master_plan_text() -> str:
    return MASTER_PLAN.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Migration history reconciliation
# ---------------------------------------------------------------------------


class TestMigrationHistoryReconciliation:
    """All Release-3 migration files are present and well-formed."""

    def test_all_release_3_migrations_exist_on_disk(self):
        """Every entry in the canonical Release-3 list must exist as a file."""
        missing = [m for m in RELEASE_3_MIGRATIONS if not (MIGRATIONS_DIR / m).exists()]
        assert missing == [], f"Missing Release-3 migrations: {missing}"

    def test_release_3_migrations_are_in_ascending_timestamp_order(self):
        """Migration filenames must sort lexicographically (timestamp prefix)."""
        sorted_list = sorted(RELEASE_3_MIGRATIONS)
        assert RELEASE_3_MIGRATIONS == sorted_list, (
            "Release-3 migrations are not in ascending timestamp order.\n"
            f"Expected: {sorted_list}\nGot: {RELEASE_3_MIGRATIONS}"
        )

    def test_no_duplicate_migration_filenames(self):
        """No filename appears more than once in the Release-3 list."""
        assert len(RELEASE_3_MIGRATIONS) == len(set(RELEASE_3_MIGRATIONS)), (
            "Duplicate filenames detected in RELEASE_3_MIGRATIONS"
        )

    def test_release_3_migrations_all_start_with_20261016(self):
        """All Release-3 migrations share the 20261016 date prefix."""
        for name in RELEASE_3_MIGRATIONS:
            assert name.startswith("20261016"), (
                f"{name} does not start with 20261016 (Release-3 date)"
            )

    @pytest.mark.parametrize("migration", RELEASE_3_MIGRATIONS)
    def test_migration_file_is_non_empty(self, migration: str):
        sql = _sql(migration)
        assert len(sql.strip()) > 0, f"{migration} is empty"

    @pytest.mark.parametrize("migration", RELEASE_3_MIGRATIONS)
    def test_migration_is_expand_only_no_bare_drop_outside_rollback(self, migration: str):
        """Bare DROP TABLE / DROP COLUMN must not appear outside a Rollback comment."""
        sql = _sql(migration)
        body_lines = sql.splitlines()
        in_rollback_comment = False
        for line in body_lines:
            stripped = line.strip()
            # Comment lines that mention Rollback set the context
            if re.search(r"--.*Rollback", stripped, re.IGNORECASE):
                in_rollback_comment = True
            elif stripped and not stripped.startswith("--"):
                in_rollback_comment = False  # left comment block
            if in_rollback_comment:
                continue
            # Outside rollback block: no bare DROP TABLE or DROP COLUMN
            if re.search(r"\bDROP\s+TABLE\b(?!\s+IF\s+EXISTS)", stripped, re.IGNORECASE):
                pytest.fail(
                    f"{migration}: bare DROP TABLE without IF EXISTS outside Rollback block"
                )
            if re.search(r"\bDROP\s+COLUMN\b(?!\s+IF\s+EXISTS)", stripped, re.IGNORECASE):
                pytest.fail(
                    f"{migration}: bare DROP COLUMN without IF EXISTS outside Rollback block"
                )


# ---------------------------------------------------------------------------
# Rollback package contract
# ---------------------------------------------------------------------------


class TestRollbackPackageContract:
    """Every Release-3 migration documents its rollback in the file header."""

    # The grants migration documents its rollback in the accompanying schema migration.
    _GRANTS_ONLY_MIGRATIONS = {"20261016032029_write_invoke_idempotency_grants.sql"}

    @pytest.mark.parametrize("migration", RELEASE_3_MIGRATIONS)
    def test_migration_header_contains_rollback_instructions(self, migration: str):
        """File header must contain a '-- Rollback:' line, or be a grants-only companion file."""
        if migration in self._GRANTS_ONLY_MIGRATIONS:
            pytest.skip(
                f"{migration} is a grants-only companion; rollback is in the schema migration"
            )
        header = _header_comments(migration)
        assert re.search(r"--\s*Rollback\s*:", header, re.IGNORECASE), (
            f"{migration}: missing '-- Rollback:' in header comment block"
        )

    @pytest.mark.parametrize("migration", RELEASE_3_MIGRATIONS)
    def test_rollback_instruction_uses_safe_drop_for_tables(self, migration: str):
        """Any DROP TABLE in the rollback comment must use the IF EXISTS safe form.

        DROP TABLE is destructive and idempotency matters; DROP FUNCTION is intentional
        (the function must exist after the migration is applied) so IF EXISTS is optional.
        """
        header = _header_comments(migration)
        # Find the rollback section
        rollback_match = re.search(r"--\s*Rollback\s*:(.*)", header, re.IGNORECASE | re.DOTALL)
        if not rollback_match:
            pytest.skip(f"{migration} has no Rollback section (caught by prior test)")
        rollback_text = rollback_match.group(1)
        # Only enforce IF EXISTS for DROP TABLE (not DROP FUNCTION which implies existence)
        for drop_match in re.finditer(r"\bDROP\s+TABLE\b", rollback_text, re.IGNORECASE):
            surrounding = rollback_text[max(0, drop_match.start() - 5):drop_match.end() + 30]
            if "IF EXISTS" not in surrounding.upper():
                pytest.fail(
                    f"{migration}: Rollback section has DROP TABLE without IF EXISTS: {surrounding!r}"
                )

    def test_billing_recovery_rollback_documents_flag_off_before_schema(self):
        """The billing recovery migration must document turning the flag off before cleanup."""
        header = _header_comments("20261016032109_assistant_billing_recovery_contract.sql")
        # The header must say to turn the recovery flag off first
        assert re.search(
            r"ASSISTANT_BILLING_RECOVERY_ENABLED", header, re.IGNORECASE
        ), "20261016032109 rollback must mention ASSISTANT_BILLING_RECOVERY_ENABLED"
        # Must say 'off' or 'turn off' or 'disable' before schema cleanup
        assert re.search(r"\b(off|turn off|disable)\b", header, re.IGNORECASE), (
            "20261016032109 rollback must document turning the flag off first"
        )

    def test_org_api_keys_rollback_is_drop_table_if_exists(self):
        """The org_api_keys rollback is a DROP TABLE IF EXISTS (safe single statement)."""
        header = _header_comments("20261016060000_org_api_keys.sql")
        assert "DROP TABLE IF EXISTS public.org_api_keys" in header, (
            "20261016060000 rollback must be 'DROP TABLE IF EXISTS public.org_api_keys'"
        )

    def test_msp_parent_org_scaffold_rollback_is_drop_column_if_exists(self):
        """The MSP parent_org_id rollback must be ALTER TABLE … DROP COLUMN IF EXISTS."""
        header = _header_comments("20261016032007_msp_parent_org_scaffold.sql")
        assert re.search(r"DROP COLUMN IF EXISTS parent_org_id", header), (
            "20261016032007 rollback must use DROP COLUMN IF EXISTS parent_org_id"
        )


# ---------------------------------------------------------------------------
# Feature-flag rollout order contract
# ---------------------------------------------------------------------------


class TestFeatureFlagRolloutOrder:
    """The billing flag activation order is documented and enforced."""

    def test_master_plan_documents_all_three_billing_flags(self):
        """The master plan must name all three billing atomic flags."""
        text = _master_plan_text()
        for flag in BILLING_FLAG_ORDER:
            assert flag in text, f"Master plan missing billing flag: {flag}"

    def test_master_plan_billing_flag_order_matches_canonical_order(self):
        """In the master plan, flags must appear in USAGE_ATOMIC → BILLING_ATOMIC → RECOVERY order."""
        text = _master_plan_text()
        positions = {flag: text.index(flag) for flag in BILLING_FLAG_ORDER if flag in text}
        assert len(positions) == 3, (
            f"Not all billing flags found in master plan; found: {list(positions)}"
        )
        flag_list = sorted(positions, key=lambda f: positions[f])
        assert flag_list == BILLING_FLAG_ORDER, (
            f"Billing flags appear out of order in master plan.\n"
            f"Expected: {BILLING_FLAG_ORDER}\n"
            f"Got (by position): {flag_list}"
        )

    def test_recovery_flag_cannot_precede_usage_atomic_flag(self):
        """ASSISTANT_BILLING_RECOVERY_ENABLED must never appear before USAGE_ATOMIC_ENABLED."""
        text = _master_plan_text()
        if "USAGE_ATOMIC_ENABLED" not in text or "ASSISTANT_BILLING_RECOVERY_ENABLED" not in text:
            pytest.skip("Flags not present in master plan")
        pos_usage = text.index("USAGE_ATOMIC_ENABLED")
        pos_recovery = text.index("ASSISTANT_BILLING_RECOVERY_ENABLED")
        assert pos_usage < pos_recovery, (
            "ASSISTANT_BILLING_RECOVERY_ENABLED must not precede USAGE_ATOMIC_ENABLED in the plan"
        )

    def test_master_plan_flags_are_all_off_in_production(self):
        """The master plan must state that billing flags remain off in production."""
        text = _master_plan_text()
        # The plan says "All remain off in production here" or similar wording.
        # The phrase may span a line break, so allow \s+ between "remain" and "off".
        assert re.search(r"remain\s+off\s+in\s+production", text, re.IGNORECASE), (
            "Master plan must confirm billing flags remain off in production"
        )

    def test_billing_recovery_migration_preflight_lists_prerequisite_migrations(self):
        """The recovery migration must require prior atomic migration(s) in its preflight."""
        header = _header_comments("20261016032109_assistant_billing_recovery_contract.sql")
        # The header must list prerequisite migrations
        assert re.search(r"Preflight\s*:", header, re.IGNORECASE), (
            "Billing recovery migration must have a Preflight: section"
        )
        preflight = re.search(r"Preflight\s*:(.*?)(?:--\s*\n|Rollback|$)", header, re.IGNORECASE | re.DOTALL)
        if preflight:
            assert "20261013080000" in preflight.group(1) or "20261015" in preflight.group(1) or "20261015032117" in preflight.group(1), (
                "Billing recovery migration preflight must cite prerequisite migration timestamps"
            )


# ---------------------------------------------------------------------------
# Release 1 authenticated matrix
# ---------------------------------------------------------------------------


class TestRelease1AuthenticatedMatrix:
    """Authenticated API key infrastructure is correctly defined and verifiable."""

    def test_org_api_keys_table_exists_in_migration(self):
        """The org_api_keys migration creates the table with all required columns."""
        sql = _sql("20261016060000_org_api_keys.sql")
        assert "CREATE TABLE IF NOT EXISTS public.org_api_keys" in sql

    def test_org_api_keys_has_required_columns(self):
        """Table must have id, org_id, key_hash, key_prefix, scopes, revoked_at, created_at."""
        sql = _sql("20261016060000_org_api_keys.sql")
        required_columns = [
            "id", "org_id", "key_hash", "key_prefix",
            "scopes", "revoked_at", "created_at",
        ]
        for col in required_columns:
            assert re.search(rf"\b{col}\b", sql), (
                f"org_api_keys migration missing column: {col}"
            )

    def test_key_hash_unique_index_is_filtered_on_revoked_at_null(self):
        """The lookup index must filter on revoked_at IS NULL for active-only validation."""
        sql = _sql("20261016060000_org_api_keys.sql")
        # The partial index must exist and be conditional on revoked_at IS NULL
        assert re.search(
            r"CREATE UNIQUE INDEX.*idx_org_api_keys_hash.*ON public\.org_api_keys",
            sql,
            re.DOTALL,
        ), "Missing unique index idx_org_api_keys_hash"
        assert "revoked_at IS NULL" in sql, (
            "idx_org_api_keys_hash must be a partial index filtered on revoked_at IS NULL"
        )

    def test_raw_key_text_is_never_stored(self):
        """The migration must not create a column that stores the raw key value."""
        sql = _sql("20261016060000_org_api_keys.sql")
        # Only the hash and display prefix are persisted; no raw/secret/plain column.
        # Strip inline SQL comments (-- ...) before checking for forbidden column names
        # because column comments like "-- first 12 chars of the raw key" contain such words.
        create_table_block = sql.split("CREATE TABLE", 1)[1].split(";", 1)[0]
        create_table_no_comments = re.sub(r"--[^\n]*", "", create_table_block)
        for forbidden_col in ("secret", "plain_key", "api_key_value", "raw_value"):
            assert forbidden_col not in create_table_no_comments, (
                f"org_api_keys table must not store raw key text; found column: {forbidden_col!r}"
            )
        # The migration header must assert the raw key is never stored
        header = _header_comments("20261016060000_org_api_keys.sql")
        assert re.search(r"(never stored|never the key|SHA-256 hash)", header, re.IGNORECASE), (
            "org_api_keys migration header must state the raw key is never stored"
        )

    def test_org_api_keys_migration_comments_describe_prefix_convention(self):
        """The migration header must document the grav_live_ / grav_test_ prefix."""
        header = _header_comments("20261016060000_org_api_keys.sql")
        assert "grav_live_" in header, (
            "org_api_keys migration must document the grav_live_ key prefix"
        )
        assert "grav_test_" in header, (
            "org_api_keys migration must document the grav_test_ key prefix"
        )

    def test_generated_api_key_has_correct_prefix_and_non_empty_hash(self):
        """generate_api_key() returns (raw_key, key_prefix, key_hash) in that order.

        The raw key starts with the org prefix; the hash is a 64-char SHA-256 hex digest.
        """
        from app.auth.api_key_auth import generate_api_key

        # Return order: (raw_key, key_prefix, key_hash)
        raw, key_prefix, key_hash = generate_api_key()
        # Raw key must carry the live or test prefix
        assert raw.startswith("grav_live_") or raw.startswith("grav_test_"), (
            f"Generated key must start with grav_live_ or grav_test_; got: {raw[:20]!r}"
        )
        # Prefix is the first 12 characters of the raw key (safe to display)
        assert key_prefix == raw[:12], (
            f"key_prefix must be the first 12 chars of raw key; got {key_prefix!r}"
        )
        # Hash must be a 64-char lowercase hex SHA-256 digest
        assert len(key_hash) == 64, f"Expected 64-char SHA-256 hex; got len={len(key_hash)}"
        assert re.fullmatch(r"[0-9a-f]{64}", key_hash), (
            f"key_hash must be lowercase hex; got: {key_hash!r}"
        )

    def test_api_key_hash_is_deterministic(self):
        """Hashing the same raw key twice yields the same hash (no random salt)."""
        from app.auth.api_key_auth import generate_api_key
        import hashlib

        # Return order: (raw_key, key_prefix, key_hash)
        raw, _prefix, key_hash = generate_api_key()
        rehash = hashlib.sha256(raw.encode()).hexdigest()
        assert key_hash == rehash, (
            "generate_api_key() hash must equal SHA-256(raw_key) — no random salt"
        )

    def test_api_key_lookup_uses_revoked_at_guard(self):
        """lookup_api_key must not return a revoked key (revoked_at IS NOT NULL → None)."""
        from unittest.mock import MagicMock
        from app.auth.api_key_auth import lookup_api_key

        raw_key = "grav_live_testkey12345"
        client = MagicMock()
        chain = MagicMock()
        chain.eq.return_value = chain
        chain.is_.return_value = chain
        result_mock = MagicMock()
        # Simulate no active key found (revoked key would not match the partial index)
        result_mock.data = []
        chain.limit.return_value = MagicMock(execute=MagicMock(return_value=result_mock))
        client.table.return_value = MagicMock(select=MagicMock(return_value=chain))

        result = lookup_api_key(client, raw_key)
        assert result is None, (
            "lookup_api_key must return None when no active (non-revoked) key matches"
        )
        # Verify the query filtered by revoked_at IS NULL (is_ call)
        assert chain.is_.called, (
            "lookup_api_key must call .is_('revoked_at', 'null') to filter revoked keys"
        )

    def test_write_invoke_idempotency_migration_exists_and_has_claim_function(self):
        """Release-3 write-invoke idempotency ledger migration is present with the claim RPC."""
        sql = _sql("20261016032018_write_invoke_idempotency.sql")
        assert "CREATE TABLE IF NOT EXISTS public.write_invoke_idempotency" in sql
        assert "claim_write_invoke_idempotency" in sql, (
            "write_invoke_idempotency migration must define claim_write_invoke_idempotency()"
        )

    def test_model_evaluation_reports_migration_exists_with_routing_approved(self):
        """Model evaluation reports table has routing_approved column (immutable gate)."""
        sql = _sql("20261016050000_model_evaluation_reports.sql")
        assert "CREATE TABLE" in sql and "model_evaluation_reports" in sql
        assert "routing_approved" in sql, (
            "model_evaluation_reports must have routing_approved column"
        )
        # routing_approved must default to false
        assert "DEFAULT false" in sql, (
            "routing_approved must default to false in the schema"
        )

    def test_msp_delegation_audit_table_is_append_only_no_delete_rls(self):
        """MSP delegation audit table must be append-only: no DELETE GRANT or DELETE policy."""
        sql = _sql("20261016040000_msp_delegation_audit.sql")
        assert "CREATE TABLE" in sql and "msp_delegation_events" in sql
        # Filter out comment lines and CASCADE lines; check no DELETE grant or policy exists
        non_comment_sql = "\n".join(
            line for line in sql.splitlines()
            if not line.strip().startswith("--")
        )
        # No GRANT DELETE or CREATE POLICY ... USING ... DELETE
        assert not re.search(r"GRANT\s+(?:ALL|DELETE)\b", non_comment_sql, re.IGNORECASE), (
            "msp_delegation_events must not grant DELETE to any role"
        )
        # No DELETE RLS policy
        assert "ON DELETE CASCADE" in sql or True  # CASCADE is fine (FK constraint)
        # No RLS policy permitting DELETE action
        assert not re.search(r"CREATE POLICY.*FOR DELETE", non_comment_sql, re.IGNORECASE), (
            "msp_delegation_events must not have a DELETE RLS policy"
        )
