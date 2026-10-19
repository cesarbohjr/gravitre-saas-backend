"""Invoices card + payment method card: safe Stripe fields and org-scoped PDFs."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from app.routers import billing as billing_router

ORG = "33333333-3333-3333-3333-333333333333"


def _settings():
    settings = MagicMock()
    settings.stripe_secret_key = "sk_test_dummy"
    return settings


def test_invoices_carry_number_and_hosted_url_and_cards_never_invent_digits(monkeypatch):
    invoices = SimpleNamespace(
        data=[
            {
                "id": "in_1",
                "number": "INV-0001",
                "hosted_invoice_url": "https://invoice.stripe.com/i/1",
                "invoice_pdf": "https://pay.stripe.com/invoice/1/pdf",
                "amount_paid": 34900,
                "currency": "usd",
                "status": "paid",
                "period_start": 1758067200,
                "period_end": 1760659200,
                "created": 1760659200,
            }
        ]
    )
    cards = SimpleNamespace(
        data=[
            {"id": "pm_1", "type": "card", "card": {"brand": "visa", "last4": "4242", "exp_month": 8, "exp_year": 2028}},
            {"id": "pm_2", "type": "card", "card": {}},
        ]
    )
    monkeypatch.setattr(billing_router.stripe.Invoice, "list", lambda **_k: invoices)
    monkeypatch.setattr(billing_router.stripe.PaymentMethod, "list", lambda **_k: cards)
    monkeypatch.setattr(
        billing_router.stripe.Customer,
        "retrieve",
        lambda _id: {"invoice_settings": {"default_payment_method": "pm_1"}},
    )
    got_invoices, methods = billing_router._fetch_invoices_and_payment_methods(
        settings=_settings(), customer_id="cus_1"
    )
    assert got_invoices[0]["number"] == "INV-0001"
    assert got_invoices[0]["hosted_invoice_url"] == "https://invoice.stripe.com/i/1"
    assert got_invoices[0]["pdf_url"] == "https://pay.stripe.com/invoice/1/pdf"
    assert got_invoices[0]["amount_cents"] == 34900
    assert methods[0] == {
        "id": "pm_1",
        "type": "card",
        "brand": "visa",
        "last4": "4242",
        "exp_month": 8,
        "exp_year": 2028,
        "is_default": True,
    }
    assert methods[1]["last4"] is None
    assert methods[1]["brand"] is None
    assert methods[1]["is_default"] is False


def test_no_stripe_customer_means_no_invoices_or_cards():
    assert billing_router._fetch_invoices_and_payment_methods(settings=_settings(), customer_id=None) == ([], [])


def _patch_ownership(monkeypatch, customer_ids: set[str]):
    monkeypatch.setattr(billing_router, "shared_service_client", lambda *_a, **_k: MagicMock())
    monkeypatch.setattr(billing_router, "_org_stripe_customer_ids", lambda _c, _o: customer_ids)


def test_invoice_pdf_refuses_another_customers_invoice(monkeypatch):
    _patch_ownership(monkeypatch, {"cus_mine"})
    monkeypatch.setattr(
        billing_router.stripe.Invoice,
        "retrieve",
        lambda _id: {"id": "in_x", "customer": "cus_someone_else", "invoice_pdf": "https://pay.stripe.com/x"},
    )
    with pytest.raises(HTTPException) as exc:
        billing_router.download_invoice_pdf("in_x", _user={"user_id": "u"}, org_id=ORG, settings=_settings())
    assert exc.value.status_code == 404


def test_invoice_pdf_returns_url_for_own_invoice(monkeypatch):
    _patch_ownership(monkeypatch, {"cus_mine"})
    monkeypatch.setattr(
        billing_router.stripe.Invoice,
        "retrieve",
        lambda _id: {"id": "in_1", "customer": "cus_mine", "invoice_pdf": "https://pay.stripe.com/1"},
    )
    response = billing_router.download_invoice_pdf("in_1", _user={"user_id": "u"}, org_id=ORG, settings=_settings())
    assert response.body == b"https://pay.stripe.com/1"
