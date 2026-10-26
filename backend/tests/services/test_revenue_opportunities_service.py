"""Revenue opportunities count only amounts recorded in the CRM."""
from __future__ import annotations

from datetime import datetime, timezone

from app.services import revenue_opportunities_service as rev

NOW = datetime(2026, 10, 26, 12, tzinfo=timezone.utc)


def _deal(deal_id: str, name: str, amount: str | None, close: str, **props: str) -> dict:
    return {"id": deal_id, "properties": {"dealname": name, "amount": amount, "closedate": close, **props}}


def test_sums_open_deals_closing_in_window_and_links_records():
    deals = [
        _deal("1", "Acme renewal", "96000", "2026-12-01T00:00:00Z", dealtype="existingbusiness"),
        _deal("2", "Northwind seats", "28800", "2026-11-15T00:00:00Z", dealtype="newbusiness"),
        _deal("3", "Far away", "50000", "2027-06-01T00:00:00Z"),
        _deal("4", "Closed", "10000", "2026-11-01T00:00:00Z", hs_is_closed="true"),
    ]
    out = rev.summarize_deals(deals, hub_id="123", now=NOW)
    assert out["total"] == 124800.0 and out["currency"] == "USD" and out["count"] == 2
    assert [r["label"] for r in out["rows"]] == ["Acme renewal", "Northwind seats"]
    assert out["rows"][0]["kind"] == "Renewal or expansion"
    assert out["rows"][0]["href"] and "123" in out["rows"][0]["href"]


def test_missing_amounts_are_not_zero_and_currencies_are_not_mixed():
    out = rev.summarize_deals([_deal("1", "No amount", None, "2026-11-01T00:00:00Z")], hub_id=None, now=NOW)
    assert out["total"] is None and out["unpricedCount"] == 1

    mixed = rev.summarize_deals(
        [
            _deal("1", "US", "1000", "2026-11-01T00:00:00Z", deal_currency_code="USD"),
            _deal("2", "EU", "5000", "2026-11-01T00:00:00Z", deal_currency_code="EUR"),
        ],
        hub_id=None,
        now=NOW,
    )
    assert mixed["currency"] == "EUR" and mixed["total"] == 5000.0
    assert mixed["otherCurrencies"] == {"USD": 1000.0}
    assert mixed["rows"][0]["href"] is None


def test_open_invoices_are_money_to_collect():
    invoices = [
        {"status": "open", "amount_remaining": 12000, "currency": "usd", "due_date": int(NOW.timestamp()) - 86400},
        {"status": "open", "amount_remaining": 3000, "currency": "usd"},
        {"status": "paid", "amount_remaining": 0, "currency": "usd"},
    ]
    out = rev.summarize_invoices(invoices, now=NOW)
    assert out == {"total": 150.0, "currency": "USD", "count": 2, "overdueCount": 1}


class _Settings:
    disable_connectors = True


def test_not_connected_reports_no_value():
    rev._cache.clear()
    out = rev.get_revenue_opportunities(object(), "org-x", _Settings(), now=NOW)  # type: ignore[arg-type]
    assert out["status"] == "not_connected" and out["total"] is None and out["toCollect"] is None
