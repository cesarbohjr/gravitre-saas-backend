"""Lightweight JSON persistence for demo seller ↔ account and product mappings."""
from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

_lock = threading.Lock()


def _empty_store() -> dict[str, Any]:
    return {"sellers": {}, "products": []}


def _read(path: str) -> dict[str, Any]:
    file_path = Path(path)
    if not file_path.exists():
        return _empty_store()
    with file_path.open(encoding="utf-8") as handle:
        return json.load(handle)


def _write(path: str, data: dict[str, Any]) -> None:
    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with file_path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2)


def save_seller_mapping(
    store_path: str,
    *,
    seller_id: str,
    account_id: str,
    display_name: str,
    contact_email: str,
) -> None:
    """Persist seller_id → Stripe Connect account id (status is always fetched live from Stripe)."""
    with _lock:
        data = _read(store_path)
        data.setdefault("sellers", {})[seller_id] = {
            "account_id": account_id,
            "display_name": display_name,
            "contact_email": contact_email,
        }
        _write(store_path, data)


def get_seller(store_path: str, seller_id: str) -> dict[str, Any] | None:
    with _lock:
        return (_read(store_path).get("sellers") or {}).get(seller_id)


def list_sellers(store_path: str) -> dict[str, dict[str, Any]]:
    with _lock:
        return dict(_read(store_path).get("sellers") or {})


def save_product(
    store_path: str,
    *,
    stripe_product_id: str,
    stripe_price_id: str,
    connected_account_id: str,
    seller_id: str,
    name: str,
    description: str,
    unit_amount: int,
    currency: str,
) -> dict[str, Any]:
    """Store platform product metadata including which connected account receives funds."""
    row = {
        "stripe_product_id": stripe_product_id,
        "stripe_price_id": stripe_price_id,
        "connected_account_id": connected_account_id,
        "seller_id": seller_id,
        "name": name,
        "description": description,
        "unit_amount": unit_amount,
        "currency": currency,
    }
    with _lock:
        data = _read(store_path)
        products: list[dict[str, Any]] = list(data.get("products") or [])
        products.append(row)
        data["products"] = products
        _write(store_path, data)
    return row


def list_products(store_path: str) -> list[dict[str, Any]]:
    with _lock:
        return list(_read(store_path).get("products") or [])
