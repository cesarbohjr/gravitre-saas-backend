"""Flagged durable Stripe metering path.

The database atomically snapshots each charge under a scoped advisory lock.
Each worker claims disjoint intents via SKIP LOCKED. A claimed intent is never
automatically reclaimed: ambiguous Stripe acceptance must be reconciled with
Stripe before operator-approved retry. This sacrifices liveness for billing
safety and prevents silent duplicate charges after Stripe's deduplication
window expires.
"""
from __future__ import annotations

from datetime import date, datetime, time, timezone
from typing import Any

import stripe

from app.config import Settings
from app.core.logging import get_logger

logger = get_logger(__name__)
SUPPORTED_METRICS = frozenset({"ai_credits", "research_lookups", "voice_minutes"})


def report_meter_intents(
    org_id: str,
    metric_type: str,
    period_start: date,
    period_end: date,
    settings: Settings,
    *,
    client: Any,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Stage, claim, submit and atomically acknowledge one org's meter intents."""
    result: dict[str, Any] = {
        "org_id": org_id, "metric": metric_type,
        "reported": False, "reported_rows": 0, "ambiguous_rows": 0,
        "dry_run": dry_run,
    }
    if metric_type not in SUPPORTED_METRICS:
        raise ValueError("Unsupported Stripe meter metric")
    if not getattr(settings, "stripe_meter_outbox_enabled", False):
        raise RuntimeError("Stripe meter outbox path must be explicitly enabled")
    if dry_run:
        result["error"] = "outbox_dry_run_requires_read_only_preview"
        return result
    if not (settings.stripe_secret_key or "").strip():
        result["error"] = "stripe_not_configured"
        return result
    if not (period_start <= datetime.now(timezone.utc).date() <= period_end):
        result["error"] = "closed_period_requires_manual_reconciliation"
        return result

    # Resolve this once, before claiming any rows. No Stripe customer = no send.
    from app.billing.stripe_metering import _get_customer_id
    customer_id = _get_customer_id(client, org_id)
    if not customer_id:
        result["error"] = "no_customer"
        return result

    included = 0
    if metric_type == "ai_credits":
        event_name = (settings.stripe_meter_event_name or "ai_credits_used").strip()
    else:
        from app.billing.service import get_plan_for_org
        plan = get_plan_for_org(client, org_id)
        if metric_type == "research_lookups":
            from app.billing.research_lookup_plan_rates import included_research_lookups_for_plan
            from app.billing.stripe_research_lookup_metering import (
                research_lookup_meter_event_name, research_lookup_metered_price_id,
            )
            included = included_research_lookups_for_plan(plan)
            event_name = research_lookup_meter_event_name(settings)
            configured = research_lookup_metered_price_id(settings)
        else:
            from app.billing.voice_minutes_plan_rates import included_voice_minutes_for_plan
            from app.billing.stripe_voice_minutes_metering import (
                voice_minutes_meter_event_name, voice_minutes_metered_price_id,
            )
            included = included_voice_minutes_for_plan(plan)
            event_name = voice_minutes_meter_event_name(settings)
            configured = voice_minutes_metered_price_id(settings)
        if not configured:
            result["error"] = "metered_price_not_configured"
            return result

    # A plan change during the period is an explicit exception in the SQL RPC.
    # Do not consume a changed allowance or silently recalculate old charges.
    stage = client.rpc("stage_stripe_meter_intents", {
        "p_org_id": org_id, "p_metric": metric_type,
        "p_period_start": period_start.isoformat(),
        "p_period_end": period_end.isoformat(),
        "p_included": included, "p_customer_id": customer_id,
        "p_event_name": event_name,
    }).execute()
    result["staged_rows"] = int(stage.data or 0)
    claims = client.rpc("claim_stripe_meter_intents", {
        "p_org_id": org_id, "p_metric": metric_type, "p_limit": 100,
    }).execute().data or []

    stripe.api_key = settings.stripe_secret_key
    for claim in claims:
        if not isinstance(claim, dict):
            raise ValueError("Invalid Stripe meter outbox claim")
        token = claim.get("claim_token")
        intent_id = claim.get("id")
        identifier = claim.get("event_identifier")
        frozen_customer = claim.get("stripe_customer_id")
        frozen_event_name = claim.get("meter_event_name")
        quantity = int(claim.get("quantity") or 0)
        if not token or not intent_id or not identifier or quantity <= 0:
            # Never send an un-fenced or unpersisted charge.
            result["error"] = "invalid_outbox_claim"
            return result

        if frozen_customer != customer_id or frozen_event_name != event_name:
            # Do not send with a newly configured customer or meter.
            try:
                client.rpc("mark_stripe_meter_ambiguous", {
                    "p_id": intent_id, "p_claim_token": token,
                }).execute()
            except Exception:
                logger.exception("meter_outbox_identity_mismatch_mark_failed")
            result["error"] = "customer_or_meter_changed_requires_reconciliation"
            result["ambiguous_rows"] += 1
            continue

        # Stripe meter-event timestamp is acceptance time. Do not backdate or
        # force a closing period's last day after Stripe's validity window.
        try:
            stripe.billing.MeterEvent.create(
                event_name=frozen_event_name,
                payload={"stripe_customer_id": frozen_customer, "value": str(quantity)},
                identifier=identifier,
                timestamp=int(datetime.now(timezone.utc).timestamp()),
            )
        except Exception as exc:  # noqa: BLE001
            # Even an HTTP failure can follow remote acceptance. Never issue
            # a second charge automatically until the event is reconciled.
            try:
                client.rpc("mark_stripe_meter_ambiguous", {
                    "p_id": intent_id, "p_claim_token": token,
                }).execute()
            except Exception:
                logger.exception("meter_outbox_ambiguity_mark_failed metric=%s", metric_type)
            result["ambiguous_rows"] += 1
            result["error"] = "stripe_outcome_requires_reconciliation"
            logger.error("meter_outbox_ambiguous metric=%s exception=%s", metric_type, type(exc).__name__)
            continue

        try:
            response = client.rpc("ack_stripe_meter_intent", {
                "p_id": intent_id, "p_claim_token": token,
            }).execute()
            if response.data is not True:
                raise RuntimeError("Outbox acknowledgement was not committed")
        except Exception:
            # Sending remains claimed; operator must reconcile against Stripe.
            result["ambiguous_rows"] += 1
            result["error"] = "stripe_sent_but_ack_unconfirmed"
            logger.exception("meter_outbox_ack_unconfirmed metric=%s", metric_type)
            continue

        result["reported_rows"] += 1
    result["reported"] = result["reported_rows"] > 0
    return result
