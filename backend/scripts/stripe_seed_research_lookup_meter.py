"""Create or reuse Stripe Billing Meter + $0.35 metered price for Research Lookups.

Usage:
  export STRIPE_SECRET_KEY=sk_test_...  # or sk_live_...
  python backend/scripts/stripe_seed_research_lookup_meter.py

Prints Railway env vars to stdout. Does not attach the price to subscriptions.
"""
from __future__ import annotations

import argparse
import os
import sys

import stripe

EVENT_NAME = "research_lookups_used"
PRODUCT_LOOKUP_KEY = "research_lookup_overage"
PRICE_LOOKUP_KEY = "research_lookup_overage_metered"
UNIT_AMOUNT_CENTS = 35  # $0.35 per lookup


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create Stripe meter + metered price for research lookup overage."
    )
    parser.add_argument(
        "--event-name",
        default=EVENT_NAME,
        help=f"Billing meter event name (default: {EVENT_NAME})",
    )
    parser.add_argument(
        "--unit-amount-cents",
        type=int,
        default=UNIT_AMOUNT_CENTS,
        help="USD cents per lookup (default: 35 = $0.35)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print intended actions without calling Stripe",
    )
    return parser.parse_args()


def _require_secret_key() -> str:
    secret = (os.getenv("STRIPE_SECRET_KEY") or "").strip()
    if not secret:
        raise SystemExit("Missing STRIPE_SECRET_KEY. Export sk_test_* or sk_live_* first.")
    return secret


def _find_meter(event_name: str, *, dry_run: bool = False):
    if dry_run:
        return None
    for meter in stripe.billing.Meter.list(limit=100).auto_paging_iter():
        if (meter.get("event_name") or "").strip() == event_name:
            return meter
    return None


def _get_or_create_meter(event_name: str, *, dry_run: bool):
    existing = _find_meter(event_name, dry_run=dry_run)
    if existing:
        return existing, False
    if dry_run:
        return {"id": "mtr_dry_run", "event_name": event_name}, True
    created = stripe.billing.Meter.create(
        display_name="Research Lookups Used",
        event_name=event_name,
        default_aggregation={"formula": "sum"},
        value_settings={"event_payload_key": "value"},
        customer_mapping={
            "type": "by_id",
            "event_payload_key": "stripe_customer_id",
        },
    )
    return created, True


def _find_product_by_lookup(lookup_key: str, *, dry_run: bool = False):
    if dry_run:
        return None
    prices = stripe.Price.list(lookup_keys=[lookup_key], active=True, limit=1)
    if prices.data:
        product_id = prices.data[0].get("product")
        if product_id:
            return stripe.Product.retrieve(product_id)
    for product in stripe.Product.list(active=True, limit=100).auto_paging_iter():
        metadata = product.get("metadata") or {}
        if (metadata.get("usage_type") or "").strip() == lookup_key:
            return product
    return None


def _get_or_create_product(*, dry_run: bool):
    existing = _find_product_by_lookup(PRODUCT_LOOKUP_KEY, dry_run=dry_run)
    if existing:
        return existing, False
    if dry_run:
        return {"id": "prod_dry_run", "name": "Research Lookup Overage"}, True
    created = stripe.Product.create(
        name="Research Lookup Overage",
        description=(
            "Pay-as-you-go live internet research lookups above plan allotment ($0.35/lookup)"
        ),
        metadata={"usage_type": PRODUCT_LOOKUP_KEY},
    )
    return created, True


def _price_matches(price, meter_id: str, unit_amount: int) -> bool:
    recurring = price.get("recurring") or {}
    return (
        (recurring.get("meter") or "") == meter_id
        and int(price.get("unit_amount") or 0) == unit_amount
        and (recurring.get("usage_type") or "") == "metered"
        and (price.get("currency") or "").lower() == "usd"
    )


def _get_or_create_price(
    product_id: str,
    meter_id: str,
    unit_amount: int,
    *,
    dry_run: bool,
):
    if not dry_run:
        price_list = stripe.Price.list(lookup_keys=[PRICE_LOOKUP_KEY], active=True, limit=1)
        if price_list.data:
            current = price_list.data[0]
            if _price_matches(current, meter_id, unit_amount):
                return current, False
    if dry_run:
        return {"id": "price_dry_run"}, True
    created = stripe.Price.create(
        product=product_id,
        currency="usd",
        unit_amount=unit_amount,
        billing_scheme="per_unit",
        recurring={
            "interval": "month",
            "usage_type": "metered",
            "meter": meter_id,
        },
        lookup_key=PRICE_LOOKUP_KEY,
        transfer_lookup_key=True,
    )
    return created, True


def main() -> int:
    args = _parse_args()
    if not args.dry_run:
        stripe.api_key = _require_secret_key()

    print("Seeding Stripe research lookup meter + price...\n")

    meter, created_meter = _get_or_create_meter(args.event_name, dry_run=args.dry_run)
    print(
        f"- Meter {args.event_name}: "
        f"{'created' if created_meter else 'reused'} ({meter['id']})"
    )

    product, created_product = _get_or_create_product(dry_run=args.dry_run)
    print(
        f"- Product research_lookup_overage: "
        f"{'created' if created_product else 'reused'} ({product['id']})"
    )

    price, created_price = _get_or_create_price(
        product["id"],
        meter["id"],
        args.unit_amount_cents,
        dry_run=args.dry_run,
    )
    print(
        f"- Price ${args.unit_amount_cents / 100:.2f}/lookup: "
        f"{'created' if created_price else 'reused'} ({price['id']})"
    )

    print("\nAdd/update these Railway variables (staging first, then prod after live PASS):")
    print(f"STRIPE_RESEARCH_LOOKUP_METER_EVENT_NAME={args.event_name}")
    print(f"STRIPE_RESEARCH_LOOKUP_METERED_PRICE_ID={price['id']}")
    print(
        "\nDo NOT attach this metered price to production subscriptions or flip "
        "INTERNET_RESEARCH_ENABLED / NEXT_PUBLIC_INTERNET_RESEARCH_ENABLED until "
        "internet-research live verification PASS."
    )
    print("\nDone.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except stripe.error.StripeError as exc:
        message = (getattr(exc, "user_message", None) or str(exc) or "Stripe API error").strip()
        print(f"Stripe error: {message}", file=sys.stderr)
        raise SystemExit(1) from exc
