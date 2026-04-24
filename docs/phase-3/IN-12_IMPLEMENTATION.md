# IN-12 — Webhook Connector (Approval-Gated, SSRF-Safe)

**Status:** Implemented  
**Authority:** docs/MASTER_PHASED_MODULE_PLAN.md Part V, IN-10/11 patterns  
**Dependencies:** IN-00, BE-20  
**Provider:** HTTP POST via httpx (no redirects)

---

## Connector Config (connectors.config)

```json
{
  "allowed_hosts": ["hooks.example.com", "api.partner.com"],
  "default_path": "/webhooks/gravitre",
  "allowed_schemes": ["https"],
  "timeout_seconds": 5,
  "max_payload_bytes": 65536,
  "retry_count": 1,
  "retry_backoff_ms": 250
}
```

**Defaults / caps**
- timeout_seconds: default 5, max 10  
- max_payload_bytes: default 65536, max 262144  
- retry_count: default 1, max 2  
- retry_backoff_ms: default 250, max 1000  
- allowed_schemes: https only (http rejected)

---

## Secrets (connector_secrets)

| Key | Required | Description |
|-----|----------|-------------|
| WEBHOOK_BEARER_TOKEN | optional | Authorization: Bearer token |
| WEBHOOK_HMAC_SECRET | optional | Signature secret |
| WEBHOOK_HEADER_<NAME> | optional | Additional headers (allowlist enforced) |

Header allowlist: **X-Event-Type**, **X-Request-Id**, **X-Gravitre-Run-Id**, **Content-Type**

---

## Step Schema

```json
{
  "type": "webhook_post",
  "config": {
    "connector_id": "<uuid>",
    "path": "/optional/override",
    "payload_input_key": "payload",
    "headers": { "X-Event-Type": "example" }
  }
}
```

**Rules**
- `connector_id` required
- `path` must start with `/`, no `..`, no query/fragment
- `payload_input_key` default `"payload"`

---

## Dry-Run (Simulation Only)

Validations:
1. connector exists, type=webhook, status=active  
2. allowed_hosts present  
3. path valid  
4. payload exists and size <= max_payload_bytes  
5. headers allowlisted + size-limited  

Output snapshot:
```
{
  simulated: true,
  target_host,
  path,
  payload_hash,
  payload_bytes,
  headers_preview
}
```
**No network calls.**

---

## Execute (Approval-Gated)

Re-validates all dry-run checks, then:
- scheme: https only
- host: exact match from allowed_hosts
- port: default only (no custom ports)
- DNS resolution check: target must resolve to **global** IPs only
- redirects disabled

Output snapshot:
```
{
  simulated: false,
  target_host,
  path,
  payload_hash,
  payload_bytes,
  status_code,
  response_time_ms,
  retry_count_used,
  request_id,
  headers_preview
}
```

---

## SSRF Protections

- Reject localhost, private, link-local, internal IPv6 ranges  
- Require DNS resolution to global IPs only  
- Pin a validated IP for connection; set **Host** header and SNI to original hostname  
- No redirects (3xx treated as failure)  
- No query params in path  
- No custom ports

---

## Audit Events (metadata only)

| Action | Metadata |
|--------|----------|
| webhook.send.requested | target_host, payload_hash, payload_bytes, request_id |
| webhook.send.sent | target_host, status_code, response_time_ms, payload_hash, payload_bytes, request_id |
| webhook.send.failed | target_host, payload_hash, payload_bytes, request_id, error_code |

**No URLs with query params, no headers, no payload contents.**

---

## Retry / Timeout

- Retries: network errors + 5xx only, max 2  
- No retries for 4xx  
- Timeout: config timeout_seconds, max 10  

---

## Stop Conditions

- Any dry-run network calls  
- Any non-allowlisted host allowed  
- Redirects followed  
- Secrets or payload contents logged  
- SSRF protections not enforceable without deps

---

## Manual DNS Rebinding Checklist

1. Configure `allowed_hosts` with a known external host.
2. Confirm `resolve_and_validate_host()` returns only global IPs.
3. Verify request connects to **pinned IP** (not hostname) with Host header set to original hostname.
4. Confirm TLS still validates hostname (no disabling of certificate checks).
5. Ensure redirects are treated as failures.
