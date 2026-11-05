import pytest

from app.connectors.managed_oauth_inputs import validate_oauth_inputs


def test_account_config_allows_only_provider_specific_non_secret_fields():
    assert validate_oauth_inputs("servicenow", {"hostname": "acme.service-now.com"}) == {"hostname": "acme.service-now.com"}
    assert validate_oauth_inputs("front", {}) == {}
    with pytest.raises(ValueError):
        validate_oauth_inputs("front", {"oauth_client_secret_override": "secret"})


@pytest.mark.parametrize("value", ["http://localhost", "127.0.0.1", "attacker.com", "acme.service-now.com.attacker.com", "user@acme.service-now.com"])
def test_auth_hostname_cannot_target_arbitrary_origins(value):
    with pytest.raises(ValueError):
        validate_oauth_inputs("servicenow", {"hostname": value})


def test_required_values_and_region_choices_are_validated():
    with pytest.raises(ValueError):
        validate_oauth_inputs("okta", {})
    with pytest.raises(ValueError):
        validate_oauth_inputs("pandadoc", {"region": "attacker.com"})
    assert validate_oauth_inputs("pandadoc", {"region": "pandadoc.eu"}) == {"region": "pandadoc.eu"}


@pytest.mark.parametrize("hostname", ["sentry.io", "us.sentry.io", "eu.sentry.io", "de.sentry.io"])
def test_sentry_collects_reviewed_api_hostname(hostname):
    assert validate_oauth_inputs("sentry", {"hostname": hostname}) == {"hostname": hostname}


@pytest.mark.parametrize("hostname", ["", "https://sentry.io", "127.0.0.1", "sentry.io.attacker.example", "attacker.example"])
def test_sentry_token_cannot_be_routed_to_an_unreviewed_host(hostname):
    with pytest.raises(ValueError):
        validate_oauth_inputs("sentry", {"hostname": hostname})
