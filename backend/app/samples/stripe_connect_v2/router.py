"""FastAPI routes for the Stripe Connect v2 sample (HTML + JSON + thin webhooks)."""
from __future__ import annotations

from html import escape
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse

from app.samples.stripe_connect_v2.accounts import (
    create_connected_account,
    create_onboarding_link,
    get_seller_account_id,
    retrieve_account_status,
)
from app.samples.stripe_connect_v2.checkout import create_checkout_session
from app.samples.stripe_connect_v2.client import get_stripe_client
from app.samples.stripe_connect_v2.config import SampleConfigError, StripeConnectSampleConfig, load_config
from app.samples.stripe_connect_v2.html import page
from app.samples.stripe_connect_v2.products import create_platform_product, list_storefront_products
from app.samples.stripe_connect_v2.store import list_sellers
from app.samples.stripe_connect_v2.webhooks import process_thin_webhook

router = APIRouter(tags=["stripe-connect-sample"])


def _get_config() -> StripeConnectSampleConfig:
    try:
        return load_config()
    except SampleConfigError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc


@router.get("/samples/stripe-connect", response_class=HTMLResponse)
async def sample_home(config: Annotated[StripeConnectSampleConfig, Depends(_get_config)]) -> str:
    body = f"""
    <h1>Stripe Connect v2 sample</h1>
    <p>Reference flow: onboard sellers → create platform products → destination charge checkout.</p>
    <div class="card">
      <h2>Flows</h2>
      <ul>
        <li><a href="/samples/stripe-connect/seller">Seller onboarding &amp; status</a></li>
        <li><a href="/samples/stripe-connect/products/new">Create a product</a></li>
        <li><a href="/samples/stripe-connect/store">Customer storefront</a></li>
      </ul>
      <p>Platform fee: <strong>{config.platform_fee_percent}%</strong> · Base URL: <code>{escape(config.app_base_url)}</code></p>
    </div>
    """
    return page("Home", body)


@router.get("/samples/stripe-connect/seller", response_class=HTMLResponse)
async def seller_page(
    config: Annotated[StripeConnectSampleConfig, Depends(_get_config)],
    account_id: Annotated[str | None, Query(alias="accountId")] = None,
    seller_id: Annotated[str | None, Query(alias="sellerId")] = "demo-seller-1",
) -> str:
    status_block = ""
    resolved_account = account_id or (get_seller_account_id(config, seller_id or "") if seller_id else None)
    if resolved_account:
        stripe_client = get_stripe_client(config)
        status = retrieve_account_status(stripe_client, resolved_account)
        badge = "ok" if status["ready_to_receive_payments"] and status["onboarding_complete"] else "warn"
        status_block = f"""
        <div class="card">
          <h2>Live account status <span class="badge {badge}">from Stripe API</span></h2>
          <p>Account: <code>{escape(status['account_id'])}</code></p>
          <p>Transfers: <code>{escape(str(status['transfers_status']))}</code></p>
          <p>Requirements: <code>{escape(str(status['requirements_status']))}</code></p>
          <p>Ready for payouts: <strong>{'Yes' if status['ready_to_receive_payments'] else 'No'}</strong></p>
          <p>Onboarding complete: <strong>{'Yes' if status['onboarding_complete'] else 'No'}</strong></p>
          <form method="post" action="/samples/stripe-connect/seller/onboard">
            <input type="hidden" name="account_id" value="{escape(resolved_account)}" />
            <button class="btn" type="submit">Onboard to collect payments</button>
          </form>
        </div>
        """

    body = f"""
    <h1>Seller onboarding</h1>
    <p>Create a v2 connected account, then redirect to Stripe-hosted onboarding.</p>
    {status_block}
    <div class="card">
      <h2>Create connected account</h2>
      <form method="post" action="/samples/stripe-connect/seller/create">
        <label>Seller ID (your app user key)</label>
        <input name="seller_id" value="{escape(seller_id or 'demo-seller-1')}" required />
        <label>Display name</label>
        <input name="display_name" placeholder="Acme Tools Inc." required />
        <label>Contact email</label>
        <input name="contact_email" type="email" placeholder="partner@example.com" required />
        <button class="btn" type="submit">Create Connect account</button>
      </form>
    </div>
    """
    return page("Seller", body)


@router.post("/samples/stripe-connect/seller/create")
async def seller_create(
    config: Annotated[StripeConnectSampleConfig, Depends(_get_config)],
    seller_id: Annotated[str, Form()],
    display_name: Annotated[str, Form()],
    contact_email: Annotated[str, Form()],
) -> RedirectResponse:
    stripe_client = get_stripe_client(config)
    result = create_connected_account(
        stripe_client,
        config,
        seller_id=seller_id.strip(),
        display_name=display_name.strip(),
        contact_email=contact_email.strip(),
    )
    return RedirectResponse(
        url=f"/samples/stripe-connect/seller?sellerId={result['seller_id']}&accountId={result['account_id']}",
        status_code=303,
    )


@router.post("/samples/stripe-connect/seller/onboard")
async def seller_onboard(
    config: Annotated[StripeConnectSampleConfig, Depends(_get_config)],
    account_id: Annotated[str, Form()],
) -> RedirectResponse:
    stripe_client = get_stripe_client(config)
    url = create_onboarding_link(stripe_client, config, account_id=account_id.strip())
    return RedirectResponse(url=url, status_code=303)


@router.get("/samples/stripe-connect/products/new", response_class=HTMLResponse)
async def product_form(config: Annotated[StripeConnectSampleConfig, Depends(_get_config)]) -> str:
    sellers = list_sellers(config.store_path)
    options = "".join(
        f'<option value="{escape(sid)}">{escape(sid)} — {escape(str(row.get("display_name") or ""))}</option>'
        for sid, row in sellers.items()
    )
    if not options:
        options = '<option value="">No sellers — create one first</option>'

    body = f"""
    <h1>Create product</h1>
    <p>Products are created on the <strong>platform</strong> and mapped to a connected account.</p>
    <div class="card">
      <form method="post" action="/samples/stripe-connect/products">
        <label>Seller</label>
        <select name="seller_id" required>{options}</select>
        <label>Product name</label>
        <input name="name" required />
        <label>Description</label>
        <textarea name="description" rows="3"></textarea>
        <label>Price (USD)</label>
        <input name="price_dollars" type="number" min="0.5" step="0.01" value="9.99" required />
        <button class="btn" type="submit">Create on platform</button>
      </form>
    </div>
    """
    return page("New product", body)


@router.post("/samples/stripe-connect/products")
async def product_create(
    config: Annotated[StripeConnectSampleConfig, Depends(_get_config)],
    seller_id: Annotated[str, Form()],
    name: Annotated[str, Form()],
    description: Annotated[str, Form()] = "",
    price_dollars: Annotated[float, Form()] = 9.99,
) -> RedirectResponse:
    account_id = get_seller_account_id(config, seller_id.strip())
    if not account_id:
        raise HTTPException(status_code=400, detail="Unknown seller — create a connected account first")

    stripe_client = get_stripe_client(config)
    create_platform_product(
        stripe_client,
        config,
        seller_id=seller_id.strip(),
        connected_account_id=account_id,
        name=name.strip(),
        description=description.strip(),
        price_cents=int(round(price_dollars * 100)),
    )
    return RedirectResponse(url="/samples/stripe-connect/store", status_code=303)


@router.get("/samples/stripe-connect/store", response_class=HTMLResponse)
async def storefront(config: Annotated[StripeConnectSampleConfig, Depends(_get_config)]) -> str:
    products = list_storefront_products(config)
    sellers = list_sellers(config.store_path)

    cards = ""
    for product in products:
        seller = sellers.get(str(product.get("seller_id") or ""), {})
        price = int(product.get("unit_amount") or 0) / 100
        cards += f"""
        <div class="card">
          <h3>{escape(str(product.get('name') or 'Product'))}</h3>
          <p>{escape(str(product.get('description') or ''))}</p>
          <p>Seller: <code>{escape(str(product.get('seller_id') or ''))}</code>
             ({escape(str(seller.get('display_name') or '—'))})</p>
          <p><strong>${price:,.2f}</strong> {escape(str(product.get('currency') or 'usd').upper())}</p>
          <form method="post" action="/samples/stripe-connect/checkout">
            <input type="hidden" name="stripe_product_id" value="{escape(str(product.get('stripe_product_id') or ''))}" />
            <button class="btn" type="submit">Buy with Checkout</button>
          </form>
        </div>
        """

    if not cards:
        cards = '<p>No products yet. <a href="/samples/stripe-connect/products/new">Create one</a>.</p>'

    body = f"""
    <h1>Storefront</h1>
    <p>Destination charges: platform collects payment, transfers to seller, keeps {config.platform_fee_percent}% fee.</p>
    <div class="grid">{cards}</div>
    """
    return page("Store", body)


@router.post("/samples/stripe-connect/checkout")
async def start_checkout(
    config: Annotated[StripeConnectSampleConfig, Depends(_get_config)],
    stripe_product_id: Annotated[str, Form()],
) -> RedirectResponse:
    products = list_storefront_products(config)
    product = next((p for p in products if p.get("stripe_product_id") == stripe_product_id), None)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found in sample store")

    stripe_client = get_stripe_client(config)
    url = create_checkout_session(stripe_client, config, product=product)
    return RedirectResponse(url=url, status_code=303)


@router.get("/samples/stripe-connect/success", response_class=HTMLResponse)
async def checkout_success(session_id: Annotated[str | None, Query(alias="session_id")] = None) -> str:
    body = f"""
    <h1>Payment successful</h1>
    <p>Checkout session: <code>{escape(session_id or '—')}</code></p>
    <p><a href="/samples/stripe-connect/store">Back to store</a></p>
    """
    return page("Success", body)


@router.post("/api/samples/stripe-connect/webhooks/thin")
async def thin_webhook(
    request: Request,
    config: Annotated[StripeConnectSampleConfig, Depends(_get_config)],
) -> dict[str, Any]:
    """Thin webhook endpoint for Connect v2 account updates.

    Configure in Dashboard → Developers → Webhooks → Add destination:
    - Events from: Connected accounts
    - Payload style: Thin
    - Events: v2.core.account[requirements].updated, capability_status_updated variants

    Local forward:
    stripe listen --thin-events 'v2.core.account[requirements].updated,v2.core.account[.recipient].capability_status_updated' \\
      --forward-thin-to http://localhost:8000/api/samples/stripe-connect/webhooks/thin
    """
    payload = await request.body()
    signature = request.headers.get("stripe-signature")
    stripe_client = get_stripe_client(config)
    try:
        return process_thin_webhook(stripe_client, config, payload=payload, signature=signature)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
