#!/usr/bin/env python3
"""Phase 0 evidence: compare Stripe subscription vs org_billing/subscriptions for an org.

Usage:
  python scripts/reconcile-org-billing-plan.py --org-name "Cesar Bohorquez Jr.'s Workspace"
  python scripts/reconcile-org-billing-plan.py --org-id <uuid>
  python scripts/reconcile-org-billing-plan.py --org-id <uuid> --apply
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))


def _load_env() -> None:
    for candidate in (
        ROOT / "backend" / ".env.operator.local",
        ROOT / "backend" / ".env",
        ROOT / ".env",
    ):
        if not candidate.exists():
            continue
        for line in candidate.read_text(encoding="utf-8", errors="ignore").splitlines():
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip("'").strip('"')
            if key and key not in os.environ:
                os.environ[key] = value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--org-id")
    parser.add_argument("--org-name")
    parser.add_argument("--apply", action="store_true", help="Write repaired plan_code/tier from Stripe")
    parser.add_argument("--json-out")
    args = parser.parse_args()

    _load_env()
    from supabase import create_client
    import stripe
    from app.config import get_settings
    from app.routers.webhooks.stripe import _resolve_plan_code
    from app.billing.stripe import init_stripe

    settings = get_settings()
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)

    org_id = (args.org_id or "").strip()
    if not org_id and args.org_name:
        orgs = (
            client.table("organizations")
            .select("id, name")
            .ilike("name", args.org_name.strip())
            .limit(5)
            .execute()
            .data
            or []
        )
        if not orgs:
            # fuzzy contains
            orgs = (
                client.table("organizations")
                .select("id, name")
                .ilike("name", f"%{args.org_name.strip()}%")
                .limit(10)
                .execute()
                .data
                or []
            )
        if not orgs:
            print(json.dumps({"error": "org_not_found", "org_name": args.org_name}))
            return 2
        if len(orgs) > 1:
            print(json.dumps({"error": "ambiguous_org", "matches": orgs}, indent=2))
            return 3
        org_id = str(orgs[0]["id"])
        org_name = str(orgs[0]["name"])
    else:
        row = (
            client.table("organizations")
            .select("id, name")
            .eq("id", org_id)
            .limit(1)
            .execute()
            .data
            or []
        )
        org_name = str(row[0]["name"]) if row else None

    billing = (
        client.table("org_billing").select("*").eq("org_id", org_id).limit(1).execute().data or []
    )
    subs = (
        client.table("subscriptions").select("*").eq("org_id", org_id).limit(1).execute().data or []
    )
    billing_row = billing[0] if billing else {}
    sub_row = subs[0] if subs else {}

    sub_id = str(
        sub_row.get("stripe_subscription_id")
        or billing_row.get("stripe_subscription_id")
        or ""
    ).strip()
    customer_id = str(
        sub_row.get("stripe_customer_id") or billing_row.get("stripe_customer_id") or ""
    ).strip()

    stripe_view: dict = {}
    resolved_plan = None
    stripe_key_present = bool(str(settings.stripe_secret_key or "").strip())
    if sub_id and stripe_key_present:
        try:
            init_stripe(settings)
            stripe_sub = stripe.Subscription.retrieve(sub_id, expand=["items.data.price"])
            data = stripe_sub.to_dict() if hasattr(stripe_sub, "to_dict") else dict(stripe_sub)
            items = []
            for item in (data.get("items") or {}).get("data") or []:
                price = item.get("price") if isinstance(item, dict) else None
                price = price if isinstance(price, dict) else {}
                recurring = price.get("recurring") if isinstance(price.get("recurring"), dict) else {}
                items.append(
                    {
                        "price_id": price.get("id"),
                        "nickname": price.get("nickname"),
                        "unit_amount": price.get("unit_amount"),
                        "usage_type": recurring.get("usage_type"),
                        "interval": recurring.get("interval"),
                    }
                )
            meta = data.get("metadata") if isinstance(data.get("metadata"), dict) else {}
            resolved_plan = _resolve_plan_code(settings, data, meta)
            stripe_view = {
                "subscription_id": data.get("id"),
                "status": data.get("status"),
                "customer": data.get("customer"),
                "metadata": meta,
                "items": items,
                "resolved_plan_code": resolved_plan,
            }
        except Exception as exc:  # noqa: BLE001
            stripe_view = {"error": str(exc), "subscription_id": sub_id}
    elif customer_id and stripe_key_present:
        try:
            init_stripe(settings)
            listed = stripe.Subscription.list(customer=customer_id, status="all", limit=5)
            stripe_view = {
                "customer": customer_id,
                "subscriptions": [
                    {
                        "id": s.id,
                        "status": s.status,
                        "items": [
                            (getattr(i.price, "id", None) if i.price else None)
                            for i in (s["items"].data if hasattr(s, "__getitem__") else s.items.data)
                        ],
                    }
                    for s in listed.data
                ],
            }
        except Exception as exc:  # noqa: BLE001
            stripe_view = {"error": str(exc), "customer": customer_id}
    else:
        stripe_view = {
            "skipped": True,
            "reason": "missing_stripe_secret_key" if not stripe_key_present else "missing_subscription_id",
        }

    report = {
        "org_id": org_id,
        "org_name": org_name,
        "db": {
            "org_billing.plan_code": billing_row.get("plan_code"),
            "org_billing.billing_status": billing_row.get("billing_status"),
            "org_billing.stripe_subscription_id": billing_row.get("stripe_subscription_id"),
            "org_billing.stripe_customer_id": billing_row.get("stripe_customer_id"),
            "subscriptions.tier": sub_row.get("tier"),
            "subscriptions.status": sub_row.get("status"),
            "subscriptions.stripe_subscription_id": sub_row.get("stripe_subscription_id"),
        },
        "stripe": stripe_view,
        "drift": {
            "db_vs_stripe": (
                None
                if not resolved_plan
                else {
                    "org_billing_matches": str(billing_row.get("plan_code") or "").lower()
                    == str(resolved_plan).lower(),
                    "subscriptions_matches": str(sub_row.get("tier") or "").lower()
                    == str(resolved_plan).lower(),
                }
            )
        },
        "applied": False,
    }

    if args.apply and resolved_plan and resolved_plan not in {"free", None}:
        now = datetime.now(timezone.utc).isoformat()
        client.table("subscriptions").upsert(
            {
                "org_id": org_id,
                "tier": resolved_plan,
                "status": stripe_view.get("status") or sub_row.get("status") or "active",
                "stripe_subscription_id": sub_id or sub_row.get("stripe_subscription_id"),
                "stripe_customer_id": customer_id or sub_row.get("stripe_customer_id"),
                "updated_at": now,
            },
            on_conflict="org_id",
        ).execute()
        client.table("org_billing").upsert(
            {
                "org_id": org_id,
                "plan_code": resolved_plan,
                "billing_status": "active"
                if stripe_view.get("status") in {None, "active", "trialing"}
                else stripe_view.get("status"),
                "stripe_subscription_id": sub_id or billing_row.get("stripe_subscription_id"),
                "stripe_customer_id": customer_id or billing_row.get("stripe_customer_id"),
                "updated_at": now,
            },
            on_conflict="org_id",
        ).execute()
        client.table("billing_events").insert(
            {
                "org_id": org_id,
                "action": "admin.plan_reconcile_from_stripe",
                "event_type": "admin.plan_reconcile_from_stripe",
                "status": "success",
                "payload": {
                    "from_org_billing": billing_row.get("plan_code"),
                    "from_subscriptions": sub_row.get("tier"),
                    "to": resolved_plan,
                    "stripe_subscription_id": sub_id,
                    "source": "scripts/reconcile-org-billing-plan.py",
                },
            }
        ).execute()
        report["applied"] = True
        report["applied_plan"] = resolved_plan

    text = json.dumps(report, indent=2, default=str)
    print(text)
    if args.json_out:
        Path(args.json_out).write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
