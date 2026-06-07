# Stripe Connect Accounts v2 — Sample Integration

Reference implementation at `backend/app/samples/stripe_connect_v2/`.

## What it demonstrates

| Step | Feature | Route |
|------|---------|-------|
| 1 | Stripe Client for all requests | `client.py` |
| 2 | Create v2 connected accounts (platform collects fees) | `POST /samples/stripe-connect/seller/create` |
| 3 | Stripe-hosted onboarding (Account Links v2) | `POST /samples/stripe-connect/seller/onboard` |
| 4 | Live account status from API (not DB) | `GET /samples/stripe-connect/seller` |
| 5 | Platform products mapped to sellers | `POST /samples/stripe-connect/products` |
| 6 | Storefront + destination charge Checkout | `GET /samples/stripe-connect/store` |
| 7 | Thin webhooks for requirements/capabilities | `POST /api/samples/stripe-connect/webhooks/thin` |

## Required environment variables

```env
# PLACEHOLDER — required
STRIPE_SECRET_KEY=sk_test_...

# PLACEHOLDER — thin Connect webhook signing secret
STRIPE_CONNECT_THIN_WEBHOOK_SECRET=whsec_...

# Public URL of this backend (for return/refresh URLs)
STRIPE_CONNECT_SAMPLE_BASE_URL=http://localhost:8000

# Optional — platform fee on destination charges (default 10)
STRIPE_CONNECT_SAMPLE_PLATFORM_FEE_PERCENT=10
```

Missing values return HTTP 503 with a clear error message.

## Run locally

```bash
cd backend
uvicorn app.main:app --reload --port 8000
```

Open http://localhost:8000/samples/stripe-connect

## Stripe Dashboard setup

### Connect platform (one-time)

Complete Connect signup in Dashboard with:

- Buyers purchase from **you** (platform)
- Sellers paid out **individually**
- Onboarding **hosted by Stripe**
- **Express** dashboard for sellers

### Thin webhook destination

1. Developers → Webhooks → **+ Add destination**
2. Events from: **Connected accounts**
3. Payload style: **Thin**
4. Events (thin / v2):
   - `v2.core.account.updated`
   - `v2.core.account.requirements.updated`
5. Endpoint URL: `https://<your-backend>/api/samples/stripe-connect/webhooks/thin`
6. Copy signing secret → `STRIPE_CONNECT_THIN_WEBHOOK_SECRET`

### Local webhook forwarding

```bash
stripe listen --thin-events "v2.core.account.updated,v2.core.account.requirements.updated" \
  --forward-thin-to http://localhost:8000/api/samples/stripe-connect/webhooks/thin
```

Or create the production destination via script (uses `STRIPE_SECRET_KEY`):

```bash
python backend/scripts/create_connect_thin_destination.py
```

## SDK

Uses `stripe` Python package with `StripeClient` (v14+). Install:

```bash
pip install "stripe>=14.4.0"
```

## Mapping to Gravitre marketplace (STA-96)

Production marketplace billing lives under `/marketplace/billing` and uses v1 Express accounts + Transfers. This sample follows Stripe's latest **Accounts v2** + **destination charge** reference. Migrate STA-96 to v2 when you are ready to adopt thin webhooks and the unified Account model.
