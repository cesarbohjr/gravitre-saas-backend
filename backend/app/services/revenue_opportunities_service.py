"""Revenue opportunities: money that already exists in the customer's own systems.

Overview › At a glance shows "Revenue opportunities". The number is the sum of
open HubSpot deal amounts that close inside the look-ahead window. Nothing is
estimated: a deal without an amount is listed as "no amount" and left out of
the total, and amounts in other currencies are kept apart rather than
converted. Open Stripe invoices are reported separately as money to collect,
never added to the opportunity total.

When no source is connected the response says so (``status`` = ``not_connected``)
and the value is ``None``, never ``0``.
"""
from __future__ import annotations

import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Any

from app.config import Settings
from app.core.logging import get_logger

logger = get_logger(__name__)

LOOKAHEAD_DAYS = 90
MAX_DEALS = 500
MAX_ROWS = 8
CACHE_TTL_SEC = 600

METHOD = (
    f"Sum of open HubSpot deal amounts closing in the next {LOOKAHEAD_DAYS} days. "
    "Only amounts recorded in your CRM count, never estimates of what a deal might grow to. "
    "Open Stripe invoices are counted separately as money to collect, not as new revenue."
)

_DEAL_PROPERTIES = [
    "dealname",
    "amount",
    "deal_currency_code",
    "closedate",
    "dealtype",
    "hs_is_closed",
    "hs_lastmodifieddate",
]

_DEAL_TYPE_LABEL = {
    "existingbusiness": "Renewal or expansion",
    "newbusiness": "New business",
}

_cache: dict[str, tuple[float, dict[str, Any]]] = {}
_cache_lock = threading.Lock()


def _to_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _parse_time(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    text = str(value).strip()
    try:
        if text.isdigit():
            return datetime.fromtimestamp(int(text) / 1000, tz=timezone.utc)
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except (ValueError, OverflowError):
        return None


def summarize_deals(
    deals: list[dict[str, Any]],
    *,
    hub_id: str | None,
    now: datetime,
    lookahead_days: int = LOOKAHEAD_DAYS,
) -> dict[str, Any]:
    """Pure: turn raw HubSpot deal search results into the opportunity summary."""
    from app.services.hubspot_urls import record_url

    horizon = now + timedelta(days=lookahead_days)
    by_currency: dict[str, float] = {}
    priced: list[dict[str, Any]] = []
    unpriced = 0
    for deal in deals:
        props = deal.get("properties") if isinstance(deal.get("properties"), dict) else {}
        if str(props.get("hs_is_closed") or "").lower() == "true":
            continue
        close = _parse_time(props.get("closedate"))
        if close is None or close > horizon:
            continue
        amount = _to_float(props.get("amount"))
        if amount is None or amount <= 0:
            unpriced += 1
            continue
        currency = str(props.get("deal_currency_code") or "USD").strip().upper() or "USD"
        by_currency[currency] = by_currency.get(currency, 0.0) + amount
        deal_id = str(deal.get("id") or "")
        kind = _DEAL_TYPE_LABEL.get(str(props.get("dealtype") or "").strip().lower(), "Open deal")
        overdue = close < now
        priced.append(
            {
                "id": deal_id,
                "label": str(props.get("dealname") or "Untitled deal").strip() or "Untitled deal",
                "kind": kind,
                "source": "HubSpot",
                "amount": round(amount, 2),
                "currency": currency,
                "closeDate": close.date().isoformat(),
                "pastCloseDate": overdue,
                "href": record_url(hub_id, object_type="deals", record_id=deal_id) if deal_id else None,
            }
        )

    if not by_currency:
        currency = "USD"
        total: float | None = 0.0 if not unpriced else None
    else:
        currency = max(by_currency, key=lambda c: by_currency[c])
        total = round(by_currency[currency], 2)
    rows = sorted((r for r in priced if r["currency"] == currency), key=lambda r: -r["amount"])
    other = {c: round(v, 2) for c, v in by_currency.items() if c != currency}
    return {
        "total": total,
        "currency": currency,
        "count": len(rows),
        "rows": rows[:MAX_ROWS],
        "moreCount": max(len(rows) - MAX_ROWS, 0),
        "otherCurrencies": other,
        "unpricedCount": unpriced,
    }


def summarize_invoices(invoices: list[dict[str, Any]], *, now: datetime) -> dict[str, Any] | None:
    """Pure: open Stripe invoices → money to collect (amounts are in minor units)."""
    by_currency: dict[str, float] = {}
    overdue = 0
    count = 0
    for inv in invoices:
        if str(inv.get("status") or "") != "open":
            continue
        remaining = _to_float(inv.get("amount_remaining"))
        if remaining is None or remaining <= 0:
            continue
        currency = str(inv.get("currency") or "usd").upper()
        by_currency[currency] = by_currency.get(currency, 0.0) + remaining / 100.0
        count += 1
        due = inv.get("due_date")
        if isinstance(due, (int, float)) and datetime.fromtimestamp(due, tz=timezone.utc) < now:
            overdue += 1
    if not by_currency:
        return {"total": 0.0, "currency": "USD", "count": 0, "overdueCount": 0}
    currency = max(by_currency, key=lambda c: by_currency[c])
    return {"total": round(by_currency[currency], 2), "currency": currency, "count": count, "overdueCount": overdue}


def _hubspot_deals(client: Any, org_id: str, settings: Settings) -> tuple[str, list[dict[str, Any]], str | None, str | None]:
    """Return (status, deals, hub_id, error)."""
    from app.connectors import hubspot
    from app.connectors.hubspot_oauth import ensure_hubspot_access_token, load_oauth_tokens
    from app.connectors.repository import get_connector_by_type
    from app.services.hubspot_urls import extract_hub_id

    conn = get_connector_by_type(client, org_id, "hubspot", environment_name="default")
    if not conn:
        return "not_connected", [], None, None
    cid = str(conn["id"])
    token, err = ensure_hubspot_access_token(
        client, org_id, cid, settings, environment_name=str(conn.get("environment") or "default")
    )
    if err or not token:
        return "needs_reconnect", [], None, "HubSpot needs to be signed in again before Gravitre can read deals."
    try:
        tokens = load_oauth_tokens(client, cid, settings, org_id=org_id)
    except Exception:  # noqa: BLE001
        tokens = None
    hub_id = extract_hub_id(conn.get("config"), tokens, conn)
    now_ms = int(time.time() * 1000)
    horizon_ms = now_ms + LOOKAHEAD_DAYS * 86_400_000
    filter_groups = [
        {
            "filters": [
                {"propertyName": "hs_is_closed", "operator": "EQ", "value": "false"},
                {"propertyName": "closedate", "operator": "LTE", "value": str(horizon_ms)},
            ]
        }
    ]
    try:
        payload = hubspot.search_crm_objects_all(
            token,
            "deals",
            filter_groups=filter_groups,
            properties=_DEAL_PROPERTIES,
            sorts=[{"propertyName": "amount", "direction": "DESCENDING"}],
            max_records=MAX_DEALS,
        )
    except hubspot.HubSpotAPIError as exc:
        logger.warning("revenue opportunities: hubspot deal search failed org_id=%s: %s", org_id, exc)
        return "error", [], hub_id, "HubSpot didn't answer just now. Try again in a few minutes."
    return "ready", list(payload.get("results") or []), hub_id, None


def _stripe_invoices(client: Any, org_id: str, settings: Settings) -> list[dict[str, Any]] | None:
    from app.services.stripe_tools import StripeAPIError, fetch_open_invoices

    try:
        return fetch_open_invoices(client, org_id, settings)
    except StripeAPIError as exc:
        logger.warning("revenue opportunities: stripe invoices failed org_id=%s: %s", org_id, exc)
        return None


def get_revenue_opportunities(
    client: Any,
    org_id: str,
    settings: Settings,
    *,
    refresh: bool = False,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Read open deals (and open invoices) for the org, cached for ten minutes."""
    if not refresh:
        with _cache_lock:
            hit = _cache.get(org_id)
        if hit and time.monotonic() - hit[0] < CACHE_TTL_SEC:
            return hit[1]

    now = now or datetime.now(timezone.utc)
    if settings.disable_connectors:
        status, deals, hub_id, error = "not_connected", [], None, None
    else:
        status, deals, hub_id, error = _hubspot_deals(client, org_id, settings)
    summary = summarize_deals(deals, hub_id=hub_id, now=now) if status == "ready" else None
    invoices = None if settings.disable_connectors else _stripe_invoices(client, org_id, settings)
    result = {
        "status": status,
        "error": error,
        "lookaheadDays": LOOKAHEAD_DAYS,
        "method": METHOD,
        "total": summary["total"] if summary else None,
        "currency": summary["currency"] if summary else "USD",
        "count": summary["count"] if summary else 0,
        "rows": summary["rows"] if summary else [],
        "moreCount": summary["moreCount"] if summary else 0,
        "otherCurrencies": summary["otherCurrencies"] if summary else {},
        "unpricedCount": summary["unpricedCount"] if summary else 0,
        "toCollect": summarize_invoices(invoices, now=now) if invoices is not None else None,
        "generatedAt": now.isoformat(),
    }
    with _cache_lock:
        _cache[org_id] = (time.monotonic(), result)
    return result
