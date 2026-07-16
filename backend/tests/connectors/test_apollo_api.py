"""Apollo API client."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.connectors.apollo_api import (
    ApolloAPIError,
    create_label,
    list_labels,
    resolve_apollo_api_key,
    search_people,
    verify_apollo_api_key,
)


def test_search_people_uses_x_api_key_header():
    with patch("app.connectors.apollo_api.httpx.Client") as client_cls:
        response = MagicMock(status_code=200, text='{"people":[]}')
        response.json.return_value = {"people": []}
        client_cls.return_value.__enter__.return_value.request.return_value = response
        out = search_people({"X-Api-Key": "secret-key"}, params={"per_page": 1})
    assert out == {"people": []}
    headers = client_cls.return_value.__enter__.return_value.request.call_args[1]["headers"]
    assert headers["X-Api-Key"] == "secret-key"


def test_verify_apollo_api_key_false_on_401():
    with patch(
        "app.connectors.apollo_api._request",
        side_effect=ApolloAPIError("bad", status_code=401),
    ):
        assert verify_apollo_api_key("bad") is False


def test_verify_apollo_api_key_true_on_plan_limit_labels():
    """Plan-limited search must not mark credentials as expired."""
    from app.connectors.apollo_api import verify_apollo_credentials

    with patch(
        "app.connectors.apollo_api._request",
        side_effect=ApolloAPIError(
            "Apollo API 403: /labels — free plan",
            status_code=403,
            details={"error": "Please upgrade your plan"},
        ),
    ):
        assert verify_apollo_credentials({"X-Api-Key": "k"}) is True


def test_is_apollo_plan_limit_error():
    from app.connectors.apollo_api import is_apollo_plan_limit_error

    assert is_apollo_plan_limit_error(
        ApolloAPIError(
            "not accessible with this access token on a free plan",
            status_code=403,
        )
    )
    assert not is_apollo_plan_limit_error(ApolloAPIError("forbidden", status_code=403))
    assert not is_apollo_plan_limit_error(ApolloAPIError("expired", status_code=401))


@patch("app.connectors.apollo_api.get_decrypted_secret")
@patch("app.connectors.apollo_api.get_connector")
def test_resolve_apollo_api_key(mock_get, mock_secret):
    mock_get.return_value = {"id": "c1"}
    mock_secret.side_effect = lambda _c, _id, key, _s: "token" if key == "api_token" else None
    settings = MagicMock()
    cid, key = resolve_apollo_api_key(MagicMock(), "org", "c1", settings)
    assert cid == "c1"
    assert key == "token"


def test_create_label_posts_name_and_modality():
    with patch("app.connectors.apollo_api.httpx.Client") as client_cls:
        response = MagicMock(status_code=200, text='{"label":{"id":"l1","name":"MSP Prospects"}}')
        response.json.return_value = {"label": {"id": "l1", "name": "MSP Prospects"}}
        client_cls.return_value.__enter__.return_value.request.return_value = response
        out = create_label({"Authorization": "Bearer token"}, name="MSP Prospects", modality="contacts")
    assert out["label"]["name"] == "MSP Prospects"
    call = client_cls.return_value.__enter__.return_value.request.call_args
    assert call[0][0] == "POST"
    assert call[0][1].endswith("/labels")
    assert call[1]["json"] == {"name": "MSP Prospects", "modality": "contacts"}


def test_create_label_422_returns_existing_label_when_duplicate():
    with patch("app.connectors.apollo_api._request") as mock_request:
        mock_request.side_effect = [
            ApolloAPIError(
                "Apollo API 422: /labels — Name has already been taken",
                status_code=422,
                details={"error": "Name has already been taken"},
            ),
            {
                "labels": [
                    {"id": "existing-1", "name": "MSP Prospects", "modality": "contacts"},
                ]
            },
        ]
        out = create_label({"X-Api-Key": "k"}, name="MSP Prospects", modality="contacts")
    assert out["already_existed"] is True
    assert out["label"]["id"] == "existing-1"
    assert mock_request.call_count == 2


def test_create_label_422_already_exists_succeeds_without_list_match():
    """Prod 2026-07-10: Apollo said already exists but GET /labels did not return the row."""
    with patch("app.connectors.apollo_api._request") as mock_request:
        mock_request.side_effect = [
            ApolloAPIError(
                "Apollo API 422: /labels — MSP Prospects already exists",
                status_code=422,
                details={"error": "MSP Prospects already exists", "skip_alert_dialog": True},
            ),
            {"labels": []},
        ]
        out = create_label({"X-Api-Key": "k"}, name="MSP Prospects", modality="contacts")
    assert out["already_existed"] is True
    assert out["label"]["name"] == "MSP Prospects"
    assert out["label"]["modality"] == "contacts"


def test_create_label_422_list_lookup_failure_still_idempotent_on_duplicate():
    with patch("app.connectors.apollo_api._request") as mock_request:
        mock_request.side_effect = [
            ApolloAPIError(
                "Apollo API 422: /labels — MSP Prospects already exists",
                status_code=422,
                details={"error": "MSP Prospects already exists"},
            ),
            ApolloAPIError("Apollo API 403: /labels", status_code=403, details={"error": "forbidden"}),
        ]
        out = create_label({"X-Api-Key": "k"}, name="MSP Prospects", modality="contacts")
    assert out["already_existed"] is True
    assert out["label"]["name"] == "MSP Prospects"


def test_create_label_422_reraises_when_not_duplicate():
    with patch("app.connectors.apollo_api._request") as mock_request:
        mock_request.side_effect = [
            ApolloAPIError(
                "Apollo API 422: /labels — modality invalid",
                status_code=422,
                details={"error": "modality invalid"},
            ),
        ]
        try:
            create_label({"X-Api-Key": "k"}, name="MSP Prospects", modality="contacts")
            assert False, "expected ApolloAPIError"
        except ApolloAPIError as exc:
            assert exc.status_code == 422
            assert "modality invalid" in str(exc)
        assert mock_request.call_count == 1


def test_apollo_error_message_includes_vendor_detail():
    with patch("app.connectors.apollo_api.httpx.Client") as client_cls:
        response = MagicMock(status_code=422, text='{"error":"Name has already been taken"}')
        response.json.return_value = {"error": "Name has already been taken"}
        client_cls.return_value.__enter__.return_value.request.return_value = response
        try:
            list_labels({"X-Api-Key": "k"})
            assert False, "expected ApolloAPIError"
        except ApolloAPIError as exc:
            assert "Name has already been taken" in str(exc)
            assert exc.details == {"error": "Name has already been taken"}


def test_list_labels_gets_labels():
    with patch("app.connectors.apollo_api.httpx.Client") as client_cls:
        response = MagicMock(status_code=200, text='{"labels":[]}')
        response.json.return_value = {"labels": []}
        client_cls.return_value.__enter__.return_value.request.return_value = response
        out = list_labels({"Authorization": "Bearer token"})
    assert out == {"labels": []}
    assert client_cls.return_value.__enter__.return_value.request.call_args[0][0] == "GET"


def test_match_person_posts_payload():
    from app.connectors.apollo_api import match_person

    with patch("app.connectors.apollo_api._request") as mock_request:
        mock_request.return_value = {"person": {"id": "p1"}}
        out = match_person({"X-Api-Key": "k"}, payload={"email": "a@b.com"})
    assert out["person"]["id"] == "p1"
    mock_request.assert_called_once_with(
        {"X-Api-Key": "k"}, "POST", "/people/match", json_body={"email": "a@b.com"}
    )


def test_enrich_organization_gets_domain():
    from app.connectors.apollo_api import enrich_organization

    with patch("app.connectors.apollo_api._request") as mock_request:
        mock_request.return_value = {"organization": {"id": "o1"}}
        out = enrich_organization({"X-Api-Key": "k"}, domain="apollo.io")
    assert out["organization"]["id"] == "o1"
    mock_request.assert_called_once_with(
        {"X-Api-Key": "k"},
        "GET",
        "/organizations/enrich",
        params={"domain": "apollo.io"},
    )
