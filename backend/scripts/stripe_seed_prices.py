from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass

import stripe


@dataclass(frozen=True)
class PlanAmounts:
    code: str
    name: str
    description: str
    monthly: int
    annual: int


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create or reuse Stripe products/prices and print env vars."
    )
    parser.add_argument("--currency", default="usd", help="ISO currency code (default: usd)")
    parser.add_argument("--node-monthly", type=int, default=5900, help="Node monthly amount in cents")
    parser.add_argument("--node-annual", type=int, default=58800, help="Node annual amount in cents")
    parser.add_argument("--control-monthly", type=int, default=14900, help="Control monthly amount in cents")
    parser.add_argument("--control-annual", type=int, default=148800, help="Control annual amount in cents")
    parser.add_argument("--command-monthly", type=int, default=34900, help="Command monthly amount in cents")
    parser.add_argument("--command-annual", type=int, default=349200, help="Command annual amount in cents")
    return parser.parse_args()


def _require_secret_key() -> str:
    secret = (os.getenv("STRIPE_SECRET_KEY") or "").strip()
    if not secret:
        raise SystemExit("Missing STRIPE_SECRET_KEY. Export it first (sk_test_* or sk_live_*).")
    return secret


def _valid_amount(amount: int) -> bool:
    return amount > 0


def _find_existing_product(plan_code: str):
    for product in stripe.Product.list(active=True, limit=100).auto_paging_iter():
        metadata = product.get("metadata") or {}
        if (metadata.get("plan_code") or "").strip().lower() == plan_code:
            return product
    return None


def _get_or_create_product(plan_code: str, name: str, description: str):
    existing = _find_existing_product(plan_code)
    if existing:
        updates: dict[str, str] = {}
        if (existing.get("name") or "") != name:
            updates["name"] = name
        if (existing.get("description") or "") != description:
            updates["description"] = description
        if updates:
            existing = stripe.Product.modify(existing["id"], **updates)
        return existing, False
    created = stripe.Product.create(name=name, description=description, metadata={"plan_code": plan_code})
    return created, True


def _price_matches(price, amount: int, currency: str, interval: str) -> bool:
    recurring = price.get("recurring") or {}
    return (
        int(price.get("unit_amount") or 0) == amount
        and (price.get("currency") or "").lower() == currency.lower()
        and (recurring.get("interval") or "").lower() == interval.lower()
    )


def _get_or_create_price(product_id: str, amount: int, currency: str, interval: str, lookup_key: str):
    price_list = stripe.Price.list(lookup_keys=[lookup_key], active=True, limit=1)
    if price_list.data:
        current = price_list.data[0]
        if _price_matches(current, amount=amount, currency=currency, interval=interval):
            return current, False
        created = stripe.Price.create(
            product=product_id,
            unit_amount=amount,
            currency=currency,
            recurring={"interval": interval},
            lookup_key=lookup_key,
            transfer_lookup_key=True,
        )
        return created, True

    created = stripe.Price.create(
        product=product_id,
        unit_amount=amount,
        currency=currency,
        recurring={"interval": interval},
        lookup_key=lookup_key,
    )
    return created, True


def main() -> int:
    args = _parse_args()
    stripe.api_key = _require_secret_key()

    plans = [
        PlanAmounts(
            "node",
            "Node",
            "Essential AI automation for individuals. Includes 1 AI agent, 10 outputs per month, 1 Core user, 2 Lite users, 3 integrations, email delivery, and community support.",
            args.node_monthly,
            args.node_annual,
        ),
        PlanAmounts(
            "control",
            "Control",
            "AI automation for growing teams. Includes 3 AI agents, 40 outputs per month, 10 Meson runs, 2 Core users, 5 Lite users, CRM & Outlook integration, multi-step execution, Slack delivery, and priority support.",
            args.control_monthly,
            args.control_annual,
        ),
        PlanAmounts(
            "command",
            "Command",
            "Full AI command center for departments. Includes 8 AI agents, 120 outputs per month, 40 Meson runs, 5 Core users, unlimited Lite users, approval workflows, advanced integrations, team workspace, custom agent training, and dedicated support.",
            args.command_monthly,
            args.command_annual,
        ),
    ]

    env_values: dict[str, str] = {}

    print("Seeding Stripe products/prices...\n")
    for plan in plans:
        if not (_valid_amount(plan.monthly) and _valid_amount(plan.annual)):
            print(
                f"- Skipping {plan.code}: monthly/annual must both be > 0 "
                f"(got {plan.monthly}/{plan.annual})."
            )
            continue

        product, created_product = _get_or_create_product(plan.code, plan.name, plan.description)
        print(f"- Product {plan.code}: {'created' if created_product else 'reused'} ({product['id']})")

        monthly_lookup = f"{plan.code}_monthly"
        annual_lookup = f"{plan.code}_annual"

        monthly_price, created_monthly = _get_or_create_price(
            product_id=product["id"],
            amount=plan.monthly,
            currency=args.currency,
            interval="month",
            lookup_key=monthly_lookup,
        )
        annual_price, created_annual = _get_or_create_price(
            product_id=product["id"],
            amount=plan.annual,
            currency=args.currency,
            interval="year",
            lookup_key=annual_lookup,
        )

        print(f"  - {monthly_lookup}: {'created' if created_monthly else 'reused'} ({monthly_price['id']})")
        print(f"  - {annual_lookup}: {'created' if created_annual else 'reused'} ({annual_price['id']})")

        env_values[f"STRIPE_PRICE_ID_{plan.code.upper()}_MONTHLY"] = monthly_price["id"]
        env_values[f"STRIPE_PRICE_ID_{plan.code.upper()}_ANNUAL"] = annual_price["id"]

    print("\nAdd/update these Railway variables:")
    for key in sorted(env_values.keys()):
        print(f"{key}={env_values[key]}")
    print("\nDone.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except stripe.error.StripeError as exc:
        message = (getattr(exc, "user_message", None) or str(exc) or "Stripe API error").strip()
        print(f"Stripe error: {message}", file=sys.stderr)
        raise SystemExit(1) from exc
