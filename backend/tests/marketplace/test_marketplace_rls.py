"""MKT-13.1: Marketplace RLS migration contract + app-layer isolation checks."""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from app.marketplace.browse import MarketplaceBrowseError, _assert_asset_browsable

REPO_ROOT = Path(__file__).resolve().parents[3]
MIGRATION_PATH = REPO_ROOT / "supabase/migrations/20260617130000_marketplace_unified_assets_schema.sql"

MARKETPLACE_TABLES = (
    "marketplace_publishers",
    "marketplace_assets",
    "marketplace_asset_versions",
    "marketplace_pack_items",
    "marketplace_installs",
    "marketplace_reviews",
    "marketplace_saves",
    "marketplace_payouts",
)

REQUIRED_POLICIES: dict[str, tuple[str, ...]] = {
    "marketplace_publishers": (
        "marketplace_publishers_select_authenticated",
        "marketplace_publishers_org_admin_write",
    ),
    "marketplace_assets": (
        "marketplace_assets_select_browse",
        "marketplace_assets_org_admin_write",
        "marketplace_assets_org_admin_update",
        "marketplace_assets_org_admin_delete",
    ),
    "marketplace_asset_versions": ("marketplace_asset_versions_select",),
    "marketplace_pack_items": ("marketplace_pack_items_select",),
    "marketplace_installs": ("marketplace_installs_org_scope",),
    "marketplace_reviews": ("marketplace_reviews_org_scope",),
    "marketplace_saves": ("marketplace_saves_org_scope",),
    "marketplace_payouts": ("marketplace_payouts_publisher_admin_select",),
}


@pytest.fixture(scope="module")
def migration_sql() -> str:
    assert MIGRATION_PATH.is_file(), f"missing migration: {MIGRATION_PATH}"
    return MIGRATION_PATH.read_text(encoding="utf-8")


def _policy_body(sql: str, policy_name: str) -> str:
    pattern = rf'CREATE POLICY "{re.escape(policy_name)}"[\s\S]*?;'
    match = re.search(pattern, sql, flags=re.IGNORECASE)
    assert match, f"policy not found: {policy_name}"
    return match.group(0)


def marketplace_asset_rls_allows(
    *,
    authenticated: bool,
    user_org_ids: set[str],
    asset: dict[str, str | None],
    publisher_org_ids: set[str] | None = None,
) -> bool:
    """Mirror marketplace_assets_select_browse (MKT-2.3) for contract tests."""
    if not authenticated:
        return False

    visibility = asset.get("visibility")
    status = asset.get("status")
    org_id = asset.get("org_id")
    publisher_org_ids = publisher_org_ids or set()

    if visibility == "public" and status == "published":
        return True
    if (
        visibility == "internal"
        and status == "published"
        and (
            (org_id and org_id in user_org_ids)
            or bool(publisher_org_ids & user_org_ids)
        )
    ):
        return True
    if org_id and org_id in user_org_ids:
        return True
    if publisher_org_ids & user_org_ids:
        return True
    return False


def org_scoped_rls_allows(*, user_org_ids: set[str], row_org_id: str) -> bool:
    """Mirror marketplace_installs/reviews/saves org_scope policies."""
    return row_org_id in user_org_ids


@pytest.mark.parametrize("table", MARKETPLACE_TABLES)
def test_migration_enables_rls(table: str, migration_sql: str) -> None:
    assert f"ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY" in migration_sql


@pytest.mark.parametrize("table,policies", REQUIRED_POLICIES.items())
def test_migration_defines_required_policies(table: str, policies: tuple[str, ...], migration_sql: str) -> None:
    for policy in policies:
        assert f'CREATE POLICY "{policy}"' in migration_sql
        assert f"ON public.{table}" in _policy_body(migration_sql, policy)


def test_assets_select_policy_allows_cross_tenant_public_catalog(migration_sql: str) -> None:
    body = _policy_body(migration_sql, "marketplace_assets_select_browse")
    assert "visibility = 'public'" in body
    assert "status = 'published'" in body
    assert "auth.uid() IS NOT NULL" in body


def test_org_scoped_policies_use_organization_members(migration_sql: str) -> None:
    for policy in (
        "marketplace_installs_org_scope",
        "marketplace_reviews_org_scope",
        "marketplace_saves_org_scope",
    ):
        body = _policy_body(migration_sql, policy)
        assert "organization_members" in body
        assert "org_id IN" in body


def test_payouts_policy_is_select_only_for_admins(migration_sql: str) -> None:
    body = _policy_body(migration_sql, "marketplace_payouts_publisher_admin_select")
    assert "FOR SELECT" in body
    assert "role = 'admin'" in body
    assert "FOR INSERT" not in body


@pytest.mark.parametrize(
    ("asset", "viewer_orgs", "allowed"),
    [
        (
            {"visibility": "public", "status": "published", "org_id": None},
            {"org-a"},
            True,
        ),
        (
            {"visibility": "public", "status": "draft", "org_id": None},
            {"org-a"},
            False,
        ),
        (
            {"visibility": "private", "status": "published", "org_id": "org-a"},
            {"org-a"},
            True,
        ),
        (
            {"visibility": "private", "status": "published", "org_id": "org-b"},
            {"org-a"},
            False,
        ),
        (
            {"visibility": "internal", "status": "published", "org_id": "org-b"},
            {"org-a"},
            False,
        ),
    ],
)
def test_simulated_asset_rls_matches_public_and_org_rules(
    asset: dict[str, str | None],
    viewer_orgs: set[str],
    allowed: bool,
) -> None:
    assert (
        marketplace_asset_rls_allows(
            authenticated=True,
            user_org_ids=viewer_orgs,
            asset=asset,
        )
        is allowed
    )


def test_simulated_org_scope_blocks_cross_tenant_install_reads() -> None:
    assert org_scoped_rls_allows(user_org_ids={"org-a"}, row_org_id="org-a")
    assert not org_scoped_rls_allows(user_org_ids={"org-a"}, row_org_id="org-b")


def test_app_browse_allows_published_public_assets_for_any_org() -> None:
    row = {"status": "published", "visibility": "public", "org_id": None}
    _assert_asset_browsable(row, org_id="org-viewer")


def test_app_browse_hides_other_org_private_assets() -> None:
    row = {"status": "published", "visibility": "private", "org_id": "org-owner"}
    with pytest.raises(MarketplaceBrowseError) as exc:
        _assert_asset_browsable(row, org_id="org-viewer")
    assert exc.value.code == "NOT_FOUND"


def test_app_browse_allows_org_owned_draft_assets() -> None:
    row = {"status": "draft", "visibility": "private", "org_id": "org-a"}
    _assert_asset_browsable(row, org_id="org-a")


def test_browse_list_filter_is_subset_of_public_rls(migration_sql: str) -> None:
    """Service-role browse list intentionally narrows to published public + org-owned rows."""
    body = _policy_body(migration_sql, "marketplace_assets_select_browse")
    assert "visibility = 'public'" in body
    assert "status = 'published'" in body
    # App layer: .eq("status", "published").or_("visibility.eq.public,org_id.eq.{org_id}")
    assert "organization_members" in body
