# Chat hotfix — Assistant request failed (expired connector OAuth)

## Symptom

UI toast **Assistant request failed** on simple messages (e.g. `hello`) in the
operator workspace. Isolated-org smoke still PASSed.

## Root cause (prod evidence)

Tip `ef529fe3…` Railway log:

```
assistant unified stream failed org_id=cbbf993b-… error=apollo token exchange failed: …
request_id=531b28c8-3054-4322-823c-517f16c07720 @ 2026-08-07T10:11:31Z
```

`ensure_generic_session` only caught `httpx.HTTPError` on refresh, but
`_exchange_token` raises **`ValueError`** on non-2xx OAuth responses. That
exception escaped through `list_connected_integrations` into the unified chat
stream and aborted every turn — including non-connector hellos.

## Fix

1. Soft-fail `ValueError` (and HTTPError) in `ensure_generic_session` → mark
   connector expired, continue.
2. Per-connector try/except in `list_connector_availability`.
3. Soft-fail wrapper in `list_connected_integrations_cached`.
4. Settings routes: use `response_error()` (supabase-py v2 has no `.error`).

## Regression tests

- `test_ensure_generic_session_soft_fails_on_valueerror_refresh`
- `test_list_connector_availability_soft_fails_one_bad_connector`
