"""MSP partner program: link/approve/detach, auth, wholesale sync, entitlements."""
from __future__ import annotations

import copy
import uuid
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

import pytest
from fastapi import HTTPException

from app.billing import msp_billing
from app.services import msp_program


# ---------------------------------------------------------------------------
# In-memory Supabase double that applies every filter
# ---------------------------------------------------------------------------


class Resp:
    def __init__(self, data, count=None):
        self.data = data
        self.count = count


class Query:
    def __init__(self, db: "Db", table: str):
        self.db, self.table = db, table
        self.op, self.payload, self.filters = "select", None, []
        self._limit = None
        self._count = None
        self.on_conflict = None

    def select(self, *_a, count=None, **_k):
        self.op = "select"
        self._count = count
        return self

    def insert(self, payload):
        self.op, self.payload = "insert", payload
        return self

    def update(self, payload):
        self.op, self.payload = "update", payload
        return self

    def upsert(self, payload, on_conflict=None):
        self.op, self.payload, self.on_conflict = "upsert", payload, on_conflict
        return self

    def delete(self):
        self.op = "delete"
        return self

    def eq(self, col, val):
        self.filters.append(lambda r, c=col, v=val: str(r.get(c)) == str(v) if v is not None else r.get(c) is None)
        return self

    def in_(self, col, vals):
        vals = {str(v) for v in vals}
        self.filters.append(lambda r, c=col: str(r.get(c)) in vals)
        return self

    def is_(self, col, val):
        self.filters.append(lambda r, c=col: r.get(c) is None)
        return self

    def gt(self, col, val):
        self.filters.append(lambda r, c=col, v=val: str(r.get(c) or "") > str(v))
        return self

    def order(self, *_a, **_k):
        return self

    def limit(self, n):
        self._limit = n
        return self

    def _match(self, row):
        return all(f(row) for f in self.filters)

    def execute(self):
        rows = self.db.tables.setdefault(self.table, [])
        self.db.log.append((self.op, self.table))
        if self.table in self.db.fail_tables:
            raise RuntimeError(f"{self.table} unavailable")
        if self.op == "select":
            found = [copy.deepcopy(r) for r in rows if self._match(r)]
            count = len(found)
            if self._limit is not None:
                found = found[: self._limit]
            return Resp(found, count if self._count else None)
        if self.op == "insert":
            batch = self.payload if isinstance(self.payload, list) else [self.payload]
            out = []
            for raw in batch:
                row = {"id": str(uuid.uuid4()), "created_at": "2026-10-19T00:00:00+00:00", **copy.deepcopy(raw)}
                self.db.check(self.table, row, rows)
                rows.append(row)
                out.append(copy.deepcopy(row))
            return Resp(out)
        if self.op == "update":
            changed = []
            for row in rows:
                if self._match(row):
                    candidate = {**row, **copy.deepcopy(self.payload)}
                    self.db.check(self.table, candidate, [r for r in rows if r is not row])
                    row.update(copy.deepcopy(self.payload))
                    changed.append(copy.deepcopy(row))
            return Resp(changed)
        if self.op == "upsert":
            key = self.on_conflict or "id"
            for row in rows:
                if str(row.get(key)) == str(self.payload.get(key)):
                    row.update(copy.deepcopy(self.payload))
                    return Resp([copy.deepcopy(row)])
            rows.append(copy.deepcopy(self.payload))
            return Resp([copy.deepcopy(self.payload)])
        if self.op == "delete":
            kept = [r for r in rows if not self._match(r)]
            removed = len(rows) - len(kept)
            self.db.tables[self.table] = kept
            return Resp([{}] * removed)
        raise AssertionError(self.op)


class Db:
    """Also enforces the migration's msp_clients invariants."""

    def __init__(self):
        self.tables: dict[str, list[dict[str, Any]]] = {}
        self.log: list[tuple[str, str]] = []
        self.rpcs: list[tuple[str, dict]] = []
        self.fail_tables: set[str] = set()

    def table(self, name):
        return Query(self, name)

    def rpc(self, name, params):
        self.rpcs.append((name, params))
        if name == "msp_revoke_delegation_atomic":
            for g in self.tables.get("msp_delegations", []):
                if g["id"] == params["p_delegation_id"]:
                    g["revoked_at"] = "now"
        return SimpleNamespace(execute=lambda: Resp(True))

    def check(self, table, row, others):
        if table != "msp_clients":
            return
        assert row["client_org_id"] != row["msp_org_id"], "msp_clients_not_self"
        if row.get("status") != "detached":
            assert self.org(row["msp_org_id"])["account_type"] == "msp"
            assert self.org(row["client_org_id"]).get("account_type", "standard") == "standard"
            assert not any(
                o["client_org_id"] == row["client_org_id"] and o.get("status") != "detached" for o in others
            ), "uq_msp_clients_live_client"

    def org(self, org_id):
        return next(o for o in self.tables["organizations"] if o["id"] == org_id)

    def rows(self, table, **match):
        return [r for r in self.tables.get(table, []) if all(r.get(k) == v for k, v in match.items())]

    # seeding
    def add_org(self, name, account_type="standard"):
        oid = str(uuid.uuid4())
        self.tables.setdefault("organizations", []).append(
            {"id": oid, "name": name, "account_type": account_type, "status": "active", "settings": {}, "parent_org_id": None}
        )
        return oid

    def add_member(self, org_id, user_id, role, name=None):
        self.tables.setdefault("organization_members", []).append(
            {"id": str(uuid.uuid4()), "org_id": org_id, "user_id": user_id, "role": role}
        )
        if name and not self.rows("users", auth_user_id=user_id):
            self.tables.setdefault("users", []).append(
                {"auth_user_id": user_id, "full_name": name, "email": f"{name.lower()}@example.com"}
            )


def settings(**overrides):
    base = dict(
        stripe_secret_key="sk_test_x",
        stripe_price_id_msp_node_wholesale="price_w_node",
        stripe_price_id_msp_control_wholesale="price_w_control",
        stripe_price_id_msp_command_wholesale="price_w_command",
        public_app_url="https://app.test",
        msp_parent_org_enabled=False,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


@pytest.fixture(autouse=True)
def _quiet(monkeypatch):
    monkeypatch.setattr(msp_program, "write_audit_event", lambda *a, **k: None)
    monkeypatch.setattr(msp_program, "invalidate_org_and_users", lambda *a, **k: None)
    monkeypatch.setattr(msp_program, "invalidate_org_state", lambda *a, **k: None)
    monkeypatch.setattr(msp_billing, "invalidate_org_state", lambda *a, **k: None)
    monkeypatch.setattr(msp_program, "get_usage_totals", lambda *a, **k: {"ai_credits": 120, "workflow_runs": 7})
    msp_billing._PRICE_CACHE.clear()


@pytest.fixture
def world():
    db = Db()
    w = SimpleNamespace(db=db)
    w.msp = db.add_org("Acme IT", "msp")
    w.other_msp = db.add_org("Rival IT", "msp")
    w.client = db.add_org("Client Co")
    w.msp_owner, w.msp_admin, w.msp_tech = "u-msp-owner", "u-msp-admin", "u-msp-tech"
    w.client_owner, w.client_admin, w.rival = "u-client-owner", "u-client-admin", "u-rival"
    db.add_member(w.msp, w.msp_owner, "owner", "Olivia")
    db.add_member(w.msp, w.msp_admin, "admin", "Adam")
    db.add_member(w.msp, w.msp_tech, "member", "Tess")
    db.add_member(w.client, w.client_owner, "owner", "Carla")
    db.add_member(w.client, w.client_admin, "admin", "Cody")
    db.add_member(w.other_msp, w.rival, "owner", "Rex")
    return w


def _link(w, plan="node", resale=9900):
    return msp_program.request_link(
        w.db, msp_org_id=w.msp, user_id=w.msp_admin, client_org_id=w.client,
        plan_code=plan, resale_price_cents=resale, resale_interval="month",
    )["client"]["id"]


# ---------------------------------------------------------------------------
# Enrollment
# ---------------------------------------------------------------------------


def test_only_owner_can_enroll(world):
    with pytest.raises(HTTPException) as exc:
        msp_program.enroll(world.db, world.client, world.client_admin)
    assert exc.value.status_code == 403
    assert msp_program.enroll(world.db, world.client, world.client_owner)["changed"] is True
    assert world.db.org(world.client)["account_type"] == "msp"


def test_managed_client_cannot_become_msp(world):
    rel = _link(world)
    assert rel
    with pytest.raises(HTTPException) as exc:
        msp_program.enroll(world.db, world.client, world.client_owner)
    assert exc.value.status_code == 409


# ---------------------------------------------------------------------------
# Link -> approve -> detach
# ---------------------------------------------------------------------------


def test_link_requires_msp_manager(world):
    for org, user in ((world.msp, world.msp_tech), (world.msp, world.client_owner), (world.client, world.client_owner)):
        with pytest.raises(HTTPException) as exc:
            msp_program.request_link(
                world.db, msp_org_id=org, user_id=user, client_org_id=world.client,
                plan_code="node", resale_price_cents=None, resale_interval="month",
            )
        assert exc.value.status_code == 403


def test_link_cannot_target_msp_missing_or_already_linked(world):
    for target in (world.other_msp, str(uuid.uuid4())):
        with pytest.raises(HTTPException) as exc:
            msp_program.request_link(
                world.db, msp_org_id=world.msp, user_id=world.msp_owner, client_org_id=target,
                plan_code="node", resale_price_cents=None, resale_interval="month",
            )
        assert exc.value.status_code == 404
    _link(world)
    with pytest.raises(HTTPException) as exc:
        msp_program.request_link(
            world.db, msp_org_id=world.other_msp, user_id=world.rival, client_org_id=world.client,
            plan_code="node", resale_price_cents=None, resale_interval="month",
        )
    assert exc.value.status_code == 409


def test_pending_request_hides_client_name_and_grants_nothing(world):
    _link(world)
    with patch.object(msp_billing, "wholesale_price_info", return_value=None):
        listing = msp_program.list_clients(world.db, settings(), msp_org_id=world.msp, user_id=world.msp_admin)
    row = listing["clients"][0]
    assert row["status"] == "pending_client_approval"
    assert row["name"] is None and row["usage"] is None and row["health"] is None
    assert world.db.org(world.client)["parent_org_id"] is None
    assert not world.db.rows("org_billing")


def test_only_client_owner_can_approve(world):
    rel = _link(world)
    for user in (world.client_admin, world.msp_owner, world.rival):
        with pytest.raises(HTTPException) as exc:
            msp_program.approve(world.db, settings(), relationship_id=rel, user_id=user,
                                access_level="full", member_user_ids=[world.msp_tech])
        assert exc.value.status_code == 403


def test_approve_full_adds_chosen_msp_members_as_admins(world):
    rel = _link(world, plan="control")
    result = msp_program.approve(world.db, settings(), relationship_id=rel, user_id=world.client_owner,
                                 access_level="full", member_user_ids=[world.msp_tech])
    assert result["status"] == "active"
    assert result["billing"]["status"] == "checkout_required"
    assert world.db.org(world.client)["parent_org_id"] == world.msp
    assert world.db.rows("organization_members", org_id=world.client, user_id=world.msp_tech)[0]["role"] == "admin"
    stored = world.db.rows("msp_clients", id=rel)[0]
    assert stored["granted_user_ids"] == [world.msp_tech]
    billing = world.db.rows("org_billing", org_id=world.client)[0]
    assert billing["billing_source"] == "msp" and billing["billed_by_org_id"] == world.msp
    assert billing["plan_code"] == "control" and billing["billing_status"] == "trialing"


def test_approve_rejects_people_outside_the_msp(world):
    rel = _link(world)
    with pytest.raises(HTTPException) as exc:
        msp_program.approve(world.db, settings(), relationship_id=rel, user_id=world.client_owner,
                            access_level="full", member_user_ids=[world.rival])
    assert exc.value.status_code == 422
    assert not world.db.rows("organization_members", org_id=world.client, user_id=world.rival)


def test_approve_health_only_reuses_delegations_without_membership(world):
    rel = _link(world)
    msp_program.approve(world.db, settings(), relationship_id=rel, user_id=world.client_owner,
                        access_level="health_only", member_user_ids=[world.msp_tech])
    assert not world.db.rows("organization_members", org_id=world.client, user_id=world.msp_tech)
    grant = world.db.rows("msp_delegations", customer_org_id=world.client)[0]
    assert grant["provider_org_id"] == world.msp and grant["grantee_user_id"] == world.msp_tech
    assert grant["tier"] == 1 and "account.health.read" in grant["actions"]
    assert grant["approved_by_customer_user_id"] == world.client_owner


def test_never_double_bill_a_workspace_with_its_own_subscription(world):
    world.db.tables["org_billing"] = [{
        "org_id": world.client, "billing_status": "active", "stripe_subscription_id": "sub_own",
        "billing_source": "self", "plan_code": "node",
    }]
    rel = _link(world)
    overview = msp_program.overview(world.db, settings(), org_id=world.client, user_id=world.client_owner)
    assert overview["pending_request"]["own_subscription_conflict"]
    with pytest.raises(HTTPException) as exc:
        msp_program.approve(world.db, settings(), relationship_id=rel, user_id=world.client_owner,
                            access_level="full", member_user_ids=[])
    assert exc.value.status_code == 409
    assert world.db.rows("msp_clients", id=rel)[0]["status"] == "pending_client_approval"


def test_client_owner_detach_removes_granted_access_and_billing(world):
    rel = _link(world)
    msp_program.approve(world.db, settings(), relationship_id=rel, user_id=world.client_owner,
                        access_level="full", member_user_ids=[world.msp_tech])
    out = msp_program.detach(world.db, settings(), relationship_id=rel, user_id=world.client_owner)
    assert out["status"] == "detached"
    assert world.db.org(world.client)["parent_org_id"] is None
    assert not world.db.rows("organization_members", org_id=world.client, user_id=world.msp_tech)
    # The client's own people are untouched.
    assert world.db.rows("organization_members", org_id=world.client, user_id=world.client_admin)
    billing = world.db.rows("org_billing", org_id=world.client)[0]
    assert billing["billing_source"] == "self" and billing["billed_by_org_id"] is None
    assert billing["billing_status"] == "trialing"


def test_detach_revokes_health_delegations(world):
    rel = _link(world)
    msp_program.approve(world.db, settings(), relationship_id=rel, user_id=world.client_owner,
                        access_level="health_only", member_user_ids=[world.msp_tech])
    msp_program.detach(world.db, settings(), relationship_id=rel, user_id=world.msp_admin)
    assert [name for name, _ in world.db.rpcs] == ["msp_revoke_delegation_atomic"]
    assert world.db.rpcs[0][1]["p_actor_user_id"] == world.msp_admin


def test_unrelated_users_cannot_detach_or_edit(world):
    rel = _link(world)
    for user in (world.rival, world.client_admin, world.msp_tech):
        with pytest.raises(HTTPException) as exc:
            msp_program.detach(world.db, settings(), relationship_id=rel, user_id=user)
        assert exc.value.status_code == 403
    # Another MSP's manager cannot touch this relationship through their own org.
    with pytest.raises(HTTPException) as exc:
        msp_program.update_terms(world.db, settings(), msp_org_id=world.other_msp, relationship_id=rel,
                                 user_id=world.rival, plan_code="command", resale_price_cents=1,
                                 resale_interval=None)
    assert exc.value.status_code == 404
    assert world.db.rows("msp_clients", id=rel)[0]["plan_code"] == "node"


def test_rival_msp_cannot_list_or_download_statement(world):
    _link(world)
    with pytest.raises(HTTPException):
        msp_program.list_clients(world.db, settings(), msp_org_id=world.msp, user_id=world.rival)
    with pytest.raises(HTTPException):
        msp_program.statement_csv(world.db, settings(), msp_org_id=world.msp, user_id=world.msp_tech, period=None)
    with patch.object(msp_billing, "wholesale_price_info", return_value=None):
        rival = msp_program.list_clients(world.db, settings(), msp_org_id=world.other_msp, user_id=world.rival)
    assert rival["clients"] == []


# ---------------------------------------------------------------------------
# Create a client workspace
# ---------------------------------------------------------------------------


def test_create_client_workspace_is_active_and_owned_by_msp_user(world):
    def create_org(name):
        oid = world.db.add_org(name)
        world.db.add_member(oid, world.msp_admin, "owner")
        return {"id": oid, "name": name}

    out = msp_program.create_client_workspace(
        world.db, settings(stripe_price_id_msp_node_wholesale="", stripe_price_id_msp_control_wholesale="",
                           stripe_price_id_msp_command_wholesale=""),
        msp_org_id=world.msp, user={"user_id": world.msp_admin}, name="New Client", plan_code="node",
        resale_price_cents=12000, resale_interval="month", create_org=create_org,
    )
    cid = out["client"]["client_org_id"]
    assert out["billing"]["status"] == "not_configured"
    assert world.db.org(cid)["parent_org_id"] == world.msp
    assert world.db.rows("msp_clients", client_org_id=cid)[0]["status"] == "active"
    assert world.db.rows("org_billing", org_id=cid)[0]["billing_source"] == "msp"


def test_members_cannot_create_client_workspaces(world):
    called = []
    with pytest.raises(HTTPException) as exc:
        msp_program.create_client_workspace(
            world.db, settings(), msp_org_id=world.msp, user={"user_id": world.msp_tech}, name="X",
            plan_code="node", resale_price_cents=None, resale_interval="month", create_org=called.append,
        )
    assert exc.value.status_code == 403 and called == []


# ---------------------------------------------------------------------------
# Wholesale quantity sync (mocked Stripe)
# ---------------------------------------------------------------------------


class FakeStripeSub(dict):
    pass


def _activate(world, client_org, plan):
    rel = msp_program.request_link(
        world.db, msp_org_id=world.msp, user_id=world.msp_owner, client_org_id=client_org,
        plan_code=plan, resale_price_cents=None, resale_interval="month",
    )["client"]["id"]
    owner = f"owner-{client_org}"
    world.db.add_member(client_org, owner, "owner")
    msp_program.approve(world.db, settings(), relationship_id=rel, user_id=owner,
                        access_level="health_only", member_user_ids=[])
    return rel


def test_quantity_sync_sets_absolute_quantities_with_proration(world):
    world.db.tables["msp_billing_accounts"] = [{"msp_org_id": world.msp, "stripe_subscription_id": "sub_w", "status": "active"}]
    second = world.db.add_org("Second Co")
    sub = {"items": {"data": [{"id": "si_node", "quantity": 0, "price": {"id": "price_w_node"}}]}}
    with patch.object(msp_billing.stripe.Subscription, "retrieve", return_value=sub), \
         patch.object(msp_billing.stripe.Subscription, "modify") as modify:
        _activate(world, world.client, "node")
        _activate(world, second, "control")
    last = modify.call_args
    assert last.args[0] == "sub_w"
    assert last.kwargs["proration_behavior"] == "create_prorations"
    assert {"id": "si_node", "quantity": 1} in last.kwargs["items"]
    assert {"price": "price_w_control", "quantity": 1} in last.kwargs["items"]
    assert msp_billing.desired_quantities(world.db, world.msp) == {"node": 1, "control": 1, "command": 0}


def test_detach_reduces_quantity(world):
    world.db.tables["msp_billing_accounts"] = [{"msp_org_id": world.msp, "stripe_subscription_id": "sub_w", "status": "active"}]
    with patch.object(msp_billing.stripe.Subscription, "retrieve",
                      return_value={"items": {"data": [{"id": "si_node", "quantity": 1, "price": {"id": "price_w_node"}}]}}), \
         patch.object(msp_billing.stripe.Subscription, "modify") as modify:
        rel = _activate(world, world.client, "node")
        modify.reset_mock()
        msp_program.detach(world.db, settings(), relationship_id=rel, user_id=world.msp_owner)
    assert modify.call_args.kwargs["items"] == [{"id": "si_node", "quantity": 0}]


def test_sync_reports_stripe_failure_without_raising(world):
    world.db.tables["msp_billing_accounts"] = [{"msp_org_id": world.msp, "stripe_subscription_id": "sub_w", "status": "active"}]
    with patch.object(msp_billing.stripe.Subscription, "retrieve",
                      side_effect=msp_billing.stripe.error.APIConnectionError("down")):
        _activate(world, world.client, "node")  # activation itself still succeeds
        result = msp_billing.sync_wholesale_quantities(world.db, settings(), world.msp)
    assert result["status"] == "error" and "Try again" in result["message"]
    assert world.db.rows("msp_clients", client_org_id=world.client)[0]["status"] == "active"


def test_checkout_needs_config_and_a_client(world):
    with pytest.raises(msp_billing.WholesaleBillingError) as exc:
        msp_billing.create_wholesale_checkout(world.db, settings(stripe_price_id_msp_node_wholesale="",
            stripe_price_id_msp_control_wholesale="", stripe_price_id_msp_command_wholesale=""),
            msp_org_id=world.msp, user_id=world.msp_owner)
    assert exc.value.code == "not_configured"
    with pytest.raises(msp_billing.WholesaleBillingError) as exc:
        msp_billing.create_wholesale_checkout(world.db, settings(), msp_org_id=world.msp, user_id=world.msp_owner)
    assert exc.value.code == "no_clients"


def test_checkout_uses_wholesale_items_and_tags_metadata(world):
    _activate(world, world.client, "command")
    with patch.object(msp_billing.stripe.Customer, "create", return_value={"id": "cus_msp"}), \
         patch.object(msp_billing.stripe.checkout.Session, "create", return_value=SimpleNamespace(url="https://stripe/x")) as create:
        url = msp_billing.create_wholesale_checkout(world.db, settings(), msp_org_id=world.msp, user_id=world.msp_owner)
    assert url == "https://stripe/x"
    kwargs = create.call_args.kwargs
    assert kwargs["line_items"] == [{"price": "price_w_command", "quantity": 1}]
    assert kwargs["metadata"]["gravitre_kind"] == "msp_wholesale"
    assert "org_id" not in kwargs["metadata"]  # never confused with the MSP's own plan
    assert world.db.rows("msp_billing_accounts", msp_org_id=world.msp)[0]["stripe_customer_id"] == "cus_msp"


# ---------------------------------------------------------------------------
# Webhook: MSP status propagates to every active client
# ---------------------------------------------------------------------------


def test_subscription_status_propagates_to_clients(world):
    world.db.tables["msp_billing_accounts"] = [{"msp_org_id": world.msp, "stripe_customer_id": "cus_msp",
                                                "stripe_subscription_id": "sub_w", "status": "active"}]
    with patch.object(msp_billing.stripe.Subscription, "retrieve", return_value={"items": {"data": []}}), \
         patch.object(msp_billing.stripe.Subscription, "modify"):
        _activate(world, world.client, "control")
    assert world.db.rows("org_billing", org_id=world.client)[0]["billing_status"] == "active"
    data = {"id": "sub_w", "customer": "cus_msp", "status": "past_due", "metadata": {"gravitre_kind": "msp_wholesale"}}
    assert msp_billing.is_wholesale_event(world.db, "customer.subscription.updated", data, data["metadata"])
    msp_billing.apply_wholesale_event(world.db, settings(), "customer.subscription.updated", data, data["metadata"])
    assert world.db.rows("org_billing", org_id=world.client)[0]["billing_status"] == "past_due"
    msp_billing.apply_wholesale_event(world.db, settings(), "customer.subscription.deleted", data, {})
    assert world.db.rows("org_billing", org_id=world.client)[0]["billing_status"] == "cancelled"


def test_spoofed_metadata_for_another_msp_is_rejected(world):
    world.db.tables["msp_billing_accounts"] = [{"msp_org_id": world.msp, "stripe_customer_id": "cus_msp",
                                                "stripe_subscription_id": "sub_w", "status": "active"}]
    data = {"id": "sub_w", "customer": "cus_msp", "status": "active",
            "metadata": {"gravitre_kind": "msp_wholesale", "msp_org_id": world.other_msp}}
    with pytest.raises(ValueError):
        msp_billing.apply_wholesale_event(world.db, settings(), "customer.subscription.updated", data, data["metadata"])


def test_webhook_routes_wholesale_events_away_from_msp_org_billing(world):
    from app.routers.webhooks import stripe as webhook

    world.db.tables["org_billing"] = [{"org_id": world.msp, "plan_code": "command", "billing_status": "active",
                                       "stripe_subscription_id": "sub_own"}]
    world.db.tables["msp_billing_accounts"] = [{"msp_org_id": world.msp, "stripe_customer_id": "cus_msp",
                                                "stripe_subscription_id": "sub_w", "status": "active"}]
    data = {"id": "sub_w", "customer": "cus_msp", "status": "trialing", "metadata": {}, "items": {"data": []}}
    webhook._apply_stripe_event(world.db, settings(), "customer.subscription.updated", data, {}, None, {"id": "evt"})
    assert world.db.rows("org_billing", org_id=world.msp)[0]["stripe_subscription_id"] == "sub_own"
    assert world.db.rows("msp_billing_accounts", msp_org_id=world.msp)[0]["status"] == "trialing"
    assert not world.db.rows("subscriptions")


# ---------------------------------------------------------------------------
# Rebilling figures and visibility
# ---------------------------------------------------------------------------


def test_margin_and_totals(world):
    rel = _link(world, plan="control", resale=25000)
    msp_program.approve(world.db, settings(), relationship_id=rel, user_id=world.client_owner,
                        access_level="full", member_user_ids=[world.msp_admin])
    info = {"monthly_cents": 10400, "currency": "usd"}
    with patch.object(msp_billing, "wholesale_price_info", return_value=info):
        listing = msp_program.list_clients(world.db, settings(), msp_org_id=world.msp, user_id=world.msp_admin)
    row = listing["clients"][0]
    assert row["name"] == "Client Co" and row["can_open"] is True
    assert row["wholesale_monthly_cents"] == 10400 and row["margin_monthly_cents"] == 14600
    assert row["usage"] == {"ai_credits": 120, "workflow_runs": 7}
    assert row["health"]["label"] == "healthy"
    assert listing["totals"]["margin_monthly_cents"] == 14600 and listing["totals"]["active_clients"] == 1


def test_health_only_without_grant_shows_billing_but_not_usage(world):
    rel = _link(world)
    msp_program.approve(world.db, settings(), relationship_id=rel, user_id=world.client_owner,
                        access_level="health_only", member_user_ids=[world.msp_tech])
    with patch.object(msp_billing, "wholesale_price_info", return_value=None), \
         patch("app.services.msp_delegated_access.authorize_live_action", return_value=False) as authz:
        listing = msp_program.list_clients(world.db, settings(), msp_org_id=world.msp, user_id=world.msp_admin)
    row = listing["clients"][0]
    assert row["can_open"] is False and row["usage"] is None and row["health"] is None
    assert row["plan_code"] == "node"
    assert {c.kwargs["grantee_user_id"] for c in authz.call_args_list} == {world.msp_admin}


def test_statement_csv(world):
    rel = _link(world, plan="node", resale=120000)
    world.db.tables["msp_clients"][0]["resale_interval"] = "year"
    msp_program.approve(world.db, settings(), relationship_id=rel, user_id=world.client_owner,
                        access_level="full", member_user_ids=[world.msp_owner])
    with patch.object(msp_billing, "wholesale_price_info", return_value={"monthly_cents": 4100, "currency": "usd"}):
        body, name = msp_program.statement_csv(world.db, settings(), msp_org_id=world.msp,
                                               user_id=world.msp_owner, period=None)
    lines = body.strip().splitlines()
    assert lines[0].startswith("client,workspace_id,plan")
    assert lines[1].startswith("Client Co,") and ",41.00,1200.00,year,100.00,59.00,usd,120,7" in lines[1]
    assert name.startswith("gravitre-rebilling-")


# ---------------------------------------------------------------------------
# Client side: billing page, self checkout, branding
# ---------------------------------------------------------------------------


def test_billed_by_and_self_checkout_block(world):
    rel = _link(world)
    msp_program.approve(world.db, settings(), relationship_id=rel, user_id=world.client_owner,
                        access_level="full", member_user_ids=[])
    info = msp_program.billed_by(world.db, world.client)
    assert info["msp_name"] == "Acme IT" and info["plan_code"] == "node"
    with patch("app.core.db.shared_service_client", return_value=world.db):
        with pytest.raises(HTTPException) as exc:
            msp_billing.assert_not_msp_billed(settings(), world.client)
        assert exc.value.status_code == 409
        msp_billing.assert_not_msp_billed(settings(), world.msp)  # MSP's own plan is unaffected


def test_overview_shows_client_its_partner(world):
    rel = _link(world)
    msp_program.approve(world.db, settings(), relationship_id=rel, user_id=world.client_owner,
                        access_level="full", member_user_ids=[])
    staff = msp_program.overview(world.db, settings(), org_id=world.client, user_id=world.client_admin)
    assert staff["managed_by"]["msp_name"] == "Acme IT" and staff["managed_by"]["can_detach"] is False
    assert staff["can_enroll"] is False
    with pytest.raises(HTTPException):
        msp_program.overview(world.db, settings(), org_id=world.client, user_id=world.rival)


def test_pending_request_lists_msp_people_by_name(world):
    _link(world)
    view = msp_program.overview(world.db, settings(), org_id=world.client, user_id=world.client_owner)
    people = {m["name"] for m in view["pending_request"]["msp_members"]}
    assert people == {"Olivia", "Adam", "Tess"}
    admin_view = msp_program.overview(world.db, settings(), org_id=world.client, user_id=world.client_admin)
    assert admin_view["pending_request"] is None


def test_branding_inherits_only_with_active_relationship(world):
    from app.services.msp_branding import apply_inherited_branding
    from app.services.branding_service import get_org_branding

    world.db.org(world.msp)["settings"] = {"enterprise": {"branding": {"logoUrl": "https://acme/logo.png", "primaryColor": "#112233"}}}
    base = get_org_branding({})
    assert "inheritedFrom" not in apply_inherited_branding(world.db, world.client, {}, base)
    rel = _link(world)
    msp_program.approve(world.db, settings(), relationship_id=rel, user_id=world.client_owner,
                        access_level="full", member_user_ids=[])
    merged = apply_inherited_branding(world.db, world.client, {}, base)
    assert merged["logoUrl"] == "https://acme/logo.png" and merged["inheritedFrom"]["name"] == "Acme IT"
    assert merged["customDomain"] is None
    own = {"enterprise": {"branding": {"primaryColor": "#445566"}}}
    assert "inheritedFrom" not in apply_inherited_branding(world.db, world.client, own, get_org_branding(own))
    msp_program.detach(world.db, settings(), relationship_id=rel, user_id=world.client_owner)
    assert "inheritedFrom" not in apply_inherited_branding(world.db, world.client, {}, base)


def test_wholesale_setup_reports_honest_status():
    assert msp_billing.wholesale_setup(settings(stripe_secret_key=""))["status"] == "not_configured"
    assert msp_billing.wholesale_setup(settings(stripe_price_id_msp_command_wholesale=""))["status"] == "partial"
    assert msp_billing.wholesale_setup(settings())["status"] == "ready"
    assert msp_billing.monthly_cents(120000, "year") == 10000
