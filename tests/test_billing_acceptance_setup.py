"""Exercise real acceptance target/fixture/price setup without provider requests."""
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import SimpleNamespace
import sys

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
from billing_acceptance_safety import ACCEPTANCE_URL, require_isolated_target, verify_test_price


def load_script(name):
    spec = spec_from_file_location(name.replace("-", "_"), SCRIPTS / (name + ".py"))
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def isolated(monkeypatch):
    monkeypatch.setenv("BILLING_ACCEPTANCE_ISOLATED", "1")
    monkeypatch.setenv("BILLING_ACCEPTANCE_ALLOWED_URL", ACCEPTANCE_URL)


@pytest.mark.parametrize("url", [ACCEPTANCE_URL, ACCEPTANCE_URL + "/", "http://127.0.0.1:54321", "http://localhost:54321"])
def test_only_explicit_acceptance_or_local_targets_allowed(isolated, url):
    require_isolated_target(url)


@pytest.mark.parametrize("url", ["https://production.supabase.co", ACCEPTANCE_URL + "?x=1", ACCEPTANCE_URL + "#x", ACCEPTANCE_URL + "/rest/v1", "https://user:password@aadnwmjzrmbvadszroqt.supabase.co", "https://localhost.attacker.invalid", "file://localhost"])
def test_reject_unsafe_targets_before_fixture_access(isolated, url):
    with pytest.raises(ValueError):
        require_isolated_target(url)


def test_remote_target_requires_immutable_allowlist_and_isolated_opt_in(isolated, monkeypatch):
    monkeypatch.setenv("BILLING_ACCEPTANCE_ALLOWED_URL", "https://production.supabase.co")
    with pytest.raises(ValueError):
        require_isolated_target("https://production.supabase.co")
    with pytest.raises(ValueError):
        require_isolated_target(ACCEPTANCE_URL)
    monkeypatch.setenv("BILLING_ACCEPTANCE_ALLOWED_URL", ACCEPTANCE_URL)
    monkeypatch.delenv("BILLING_ACCEPTANCE_ISOLATED")
    with pytest.raises(ValueError):
        require_isolated_target(ACCEPTANCE_URL)


def test_dedicated_project_seeds_real_founder_and_customer_roles(isolated, monkeypatch):
    module = load_script("billing-e2e-fixtures")
    writes = []
    class Table:
        def insert(self, row):
            writes.append(row)
            return self
        def upsert(self, row):
            writes.append(row)
            return self
        def execute(self):
            return SimpleNamespace(data=[])
    monkeypatch.setattr(module, "_load_env", lambda: {"SUPABASE_URL": ACCEPTANCE_URL})
    monkeypatch.setattr(module, "_supabase_client", lambda _: SimpleNamespace(table=lambda _: Table()))
    monkeypatch.setattr(module, "_create_user", lambda _, label: (label + "-org", label + "-user", label + "@example.invalid", "synthetic-password"))
    monkeypatch.setattr(module, "_complete_onboarding", lambda *_: None)
    monkeypatch.setattr(module, "_set_trial_window", lambda *_, **__: None)
    fixtures = module.build_fixtures()
    assert fixtures["founder"]["userId"] == "founder-user"
    assert fixtures["founderTrialCustomer"]["orgId"] == "founder-trial-org"
    assert any(row.get("user_id") == "founder-user" for row in writes)
    assert any(row.get("customer_category") == "external" for row in writes)


def valid_price():
    return {"livemode": False, "active": True, "currency": "usd", "unit_amount": 5900,
            "recurring": {"interval": "month", "interval_count": 1, "usage_type": "licensed"}}


def test_original_invoice_price_contract_is_preserved():
    verify_test_price(valid_price())


@pytest.mark.parametrize("override", [{"livemode": True}, {"active": False}, {"unit_amount": 7900}, {"currency": "cad"}, {"recurring": {"interval": "year"}}, {"recurring": {"interval": "month", "interval_count": 1, "usage_type": "metered"}}])
def test_wrong_price_is_rejected_without_starting_listener(isolated, monkeypatch, override):
    module = load_script("prepare-dedicated-billing-acceptance")
    monkeypatch.setenv("SUPABASE_URL", ACCEPTANCE_URL)
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_synthetic")
    monkeypatch.setenv("NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY", "pk_test_synthetic")
    monkeypatch.setenv("STRIPE_PRICE_ID_NODE_MONTHLY", "price_synthetic")
    client = SimpleNamespace(v1=SimpleNamespace(prices=SimpleNamespace(retrieve=lambda _: {**valid_price(), **override})))
    with pytest.raises(ValueError):
        module.prepare(client_factory=lambda _: client, popen=lambda *_, **__: pytest.fail("Listener must not start"))


def test_missing_public_key_fails_before_stripe_or_database_access(isolated, monkeypatch):
    module = load_script("prepare-dedicated-billing-acceptance")
    monkeypatch.setenv("SUPABASE_URL", ACCEPTANCE_URL)
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_synthetic")
    monkeypatch.delenv("NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY", raising=False)
    with pytest.raises(ValueError, match="pk_test_"):
        module.prepare(client_factory=lambda _: pytest.fail("No provider request allowed"))


@pytest.mark.parametrize("price_id", ["prod_synthetic", " price_synthetic", "price_synthetic\n", '"price_synthetic"', ""])
def test_product_ids_or_decorated_price_ids_rejected_before_provider_access(isolated, monkeypatch, price_id):
    module = load_script("prepare-dedicated-billing-acceptance")
    for name, value in {"SUPABASE_URL": ACCEPTANCE_URL, "STRIPE_SECRET_KEY": "sk_test_synthetic", "NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY": "pk_test_synthetic", "STRIPE_PRICE_ID_NODE_MONTHLY": price_id}.items():
        monkeypatch.setenv(name, value)
    with pytest.raises(ValueError, match="Price ID starting price_"):
        module.prepare(client_factory=lambda _: pytest.fail("No provider request allowed"))


def test_price_lookup_failure_has_safe_class_code_without_credentials(isolated, monkeypatch):
    module = load_script("prepare-dedicated-billing-acceptance")
    for name, value in {"SUPABASE_URL": ACCEPTANCE_URL, "STRIPE_SECRET_KEY": "sk_test_synthetic", "NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY": "pk_test_synthetic", "STRIPE_PRICE_ID_NODE_MONTHLY": "price_synthetic"}.items():
        monkeypatch.setenv(name, value)
    class InvalidRequestError(Exception):
        code = "resource_missing"
        http_status = 404
    def retrieve(_):
        raise InvalidRequestError("Never print sk_test_synthetic or price_synthetic")
    client = SimpleNamespace(v1=SimpleNamespace(prices=SimpleNamespace(retrieve=retrieve)))
    with pytest.raises(ValueError) as error:
        module.prepare(client_factory=lambda _: client)
    message = str(error.value)
    assert "error=InvalidRequestError, code=resource_missing, http_status=404" in message
    assert "sk_test_synthetic" not in message and "price_synthetic" not in message


def test_listener_is_test_only_signed_and_points_to_runner(isolated, monkeypatch, tmp_path, capsys):
    module = load_script("prepare-dedicated-billing-acceptance")
    for name, value in {"SUPABASE_URL": ACCEPTANCE_URL, "STRIPE_SECRET_KEY": "sk_test_synthetic", "NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY": "pk_test_synthetic", "STRIPE_PRICE_ID_NODE_MONTHLY": "price_synthetic", "RUNNER_TEMP": str(tmp_path), "GITHUB_ENV": str(tmp_path / "env")}.items():
        monkeypatch.setenv(name, value)
    client = SimpleNamespace(v1=SimpleNamespace(prices=SimpleNamespace(retrieve=lambda _: valid_price())))
    def popen(command, **kwargs):
        assert "--live" not in command
        assert "http://127.0.0.1:8000/api/webhooks/stripe" in command
        assert "sk_test_synthetic" not in command
        assert kwargs["env"]["STRIPE_API_KEY"] == "sk_test_synthetic"
        kwargs["stdout"].write("Ready whsec_synthetic\n")
        kwargs["stdout"].flush()
        return SimpleNamespace(pid=12345, poll=lambda: None)
    module.prepare(client_factory=lambda _: client, popen=popen)
    assert (tmp_path / "env").read_text() == "STRIPE_WEBHOOK_SECRET=whsec_synthetic\n"
    assert (tmp_path / "dedicated-billing-stripe-listener.pid").read_text() == "12345"
    output = capsys.readouterr().out
    assert "::add-mask::whsec_synthetic" in output
    assert "sk_test_synthetic" not in output and "pk_test_synthetic" not in output
