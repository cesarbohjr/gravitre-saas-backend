# Private connector runtime (STA-98)

Enterprise orgs can upload **signed** connector bundles that run in an isolated subprocess sandbox (not in the main API process).

## Flow

1. Generate an Ed25519 keypair (keep private key off Gravitre).
2. Package `manifest.json` + `handlers.py` per [connector-sdk-spec.md](./connector-sdk-spec.md).
3. Sign the canonical bundle payload and upload via `POST /api/marketplace/private-bundles`.
4. Org admin activates the bundle → `invoke_tool` resolves `{vendor}.{action}` to the sandbox for that org only.

Public marketplace connectors (STA-71) still run in-process; private bundles always use the sandbox.

## Key generation

```bash
cd backend
python scripts/generate_private_connector_keypair.py --out-dir ./keys
```

## Signing

```bash
cd backend
python scripts/sign_private_connector_bundle.py \
  --manifest ../docs/integration/examples/acme-tools/manifest.json \
  --handlers ./path/to/handlers.py \
  --private-key ./keys/private-connector-signing-private.pem
```

Upload the JSON output `signature` + `packageSources` with your manifest and the **public** PEM.

## API

| Method | Path | Role |
|--------|------|------|
| GET | `/api/marketplace/private-bundles` | member |
| POST | `/api/marketplace/private-bundles` | member |
| POST | `/api/marketplace/private-bundles/{id}/activate` | admin |
| POST | `/api/marketplace/private-bundles/{id}/disable` | admin |

## Handler contract

- One file: `handlers.py`
- Function per action: `tickets.list` → `def tickets_list(ctx, params)`
- Return dict with `success`, `action`, `data` (same shape as `NormalizedResult`)
- `ctx` exposes `org_id`, `user_id`, `connector_id`, `run_id` only (no DB client in sandbox)

## Environment

```env
PRIVATE_CONNECTOR_RUNTIME_ENABLED=true
PRIVATE_CONNECTOR_SANDBOX_TIMEOUT_SEC=10
```

## Security

- Ed25519 signature over `gravitre-private-bundle-v1` + SHA-256 of canonical manifest+sources JSON
- STA-97 static analysis runs on upload; critical findings block upload/activation
- Sandbox blocks `eval`, `exec`, `__import__`, `open`, subprocess, etc.
