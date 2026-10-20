"""Endpoint contract: no cross-tenant health read without a fresh action grant."""
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.routers.msp_delegations import delegated_customer_health


class Query:
    def __init__(self, expected_id):
        self.expected_id = expected_id
        self.read_id = None
    def select(self, columns):
        assert columns == "id,status"
        return self
    def eq(self, field, value):
        assert field == "id"
        self.read_id = value
        return self
    def limit(self, n):
        assert n == 1
        return self
    def execute(self):
        return SimpleNamespace(data=[{"id": self.expected_id, "status": "active"}])


class FakeDb:
    def __init__(self, org_id):
        self.query = Query(org_id)
    def table(self, name):
        assert name == "organizations"
        return self.query


def test_disabled_feature_never_reaches_database():
    with pytest.raises(HTTPException) as exc:
        delegated_customer_health(uuid4(), uuid4(), {"user_id": "user"},
                                  SimpleNamespace(msp_parent_org_enabled=False))
    assert exc.value.status_code == 403


def test_denied_action_never_reads_customer_resource():
    customer, provider = uuid4(), uuid4()
    with patch("app.routers.msp_delegations.shared_service_client", return_value=FakeDb(str(customer))), \
         patch("app.services.msp_delegated_access.authorize_live_action", return_value=False):
        with pytest.raises(HTTPException) as exc:
            delegated_customer_health(customer, provider, {"user_id": "user"},
                SimpleNamespace(msp_parent_org_enabled=True))
    assert exc.value.status_code == 403


def test_authorized_response_is_exact_customer_projection():
    customer, provider = uuid4(), uuid4()
    db = FakeDb(str(customer))
    with patch("app.routers.msp_delegations.shared_service_client", return_value=db), \
         patch("app.services.msp_delegated_access.authorize_live_action", return_value=True) as authorize:
        result = delegated_customer_health(customer, provider, {"user_id": "user"},
            SimpleNamespace(msp_parent_org_enabled=True))
    assert result == {"customer_org_id": str(customer), "status": "active"}
    assert db.query.read_id == str(customer)
    assert authorize.call_args.kwargs["action"] == "account.health.read"


def test_wrong_customer_result_is_never_returned():
    with patch("app.routers.msp_delegations.shared_service_client",
               return_value=FakeDb(str(uuid4()))), \
         patch("app.services.msp_delegated_access.authorize_live_action", return_value=True):
        with pytest.raises(HTTPException) as exc:
            delegated_customer_health(uuid4(), uuid4(), {"user_id": "user"},
                SimpleNamespace(msp_parent_org_enabled=True))
    assert exc.value.status_code == 403
