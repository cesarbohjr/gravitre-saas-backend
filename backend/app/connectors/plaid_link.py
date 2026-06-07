"""Plaid Link integration (NOT generic OAuth callback).

Platform env: PLAID_CLIENT_ID + PLAID_SECRET (sandbox/development/production).
Per-org flow:
  1. Frontend initializes Plaid Link with platform client_id
  2. User completes institution login in Plaid Link UI
  3. Frontend receives public_token
  4. Backend exchanges public_token via /item/public_token/exchange

Do not register Plaid in oauth_provider_registry or /api/connectors/oauth/plaid/*.
"""

PLAID_LINK_ARCHITECTURE = "public_token_exchange"
