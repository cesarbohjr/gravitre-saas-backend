# IN-11 — Email Connector Implementation

**Status:** Implemented  
**Authority:** docs/MASTER_PHASED_MODULE_PLAN.md Part V, IN-10 patterns  
**Dependencies:** IN-00, BE-20  
**Provider:** SMTP (Option A)

---

## Step Type: email_send

- **Dry-run:** Simulated only. Validates connector_id, required parameters. Output: to_domain, subject_hash, body_hash, content_type. **No network calls.**
- **Execute:** Sends via SMTP only after BE-20 approvals. Uses connector secrets. **connector_id required.**

---

## Connector Secrets (SMTP)

| Key | Required | Description |
|-----|----------|-------------|
| SMTP_HOST | yes | SMTP server hostname |
| SMTP_PORT | no | Port (default 587 with TLS, 25 without) |
| SMTP_USERNAME | no | Auth username |
| SMTP_PASSWORD | no | Auth password |
| SMTP_FROM | yes | From address |

Store via `POST /api/connectors/:id/secrets` for each key.

---

## Step Schema

```json
{
  "type": "email_send",
  "config": {
    "connector_id": "<uuid>",
    "to_input_key": "to",
    "subject_input_key": "subject",
    "body_input_key": "body",
    "content_type": "text/plain"
  }
}
```

| Config Key | Required | Default | Description |
|------------|----------|---------|-------------|
| connector_id | yes | — | Connector UUID (must exist and be type email) |
| to_input_key | no | "to" | Parameters key for recipient |
| subject_input_key | no | "subject" | Parameters key for subject |
| body_input_key | no | "body" | Parameters key for body |
| content_type | no | "text/plain" | "text/plain" or "text/html" |

Connector config may include `use_tls` (default true) and `default_sender_name` (optional).

---

## Dry-Run vs Execute

| Mode | Behavior |
|------|----------|
| Dry-run | Validates connector_id exists, parameters present. Output: to_domain, subject_hash, body_hash, content_type, simulated=true. **No email sent.** |
| Execute | Loads secrets, sends via SMTP. Output: message_id (if available), to_domain, subject_hash, body_hash, content_type, simulated=false. **Runs only after approvals.** |

---

## Audit Events

| Action | When | Metadata |
|--------|------|----------|
| email.send.requested | Before send | step_id, to_domain, subject_hash, body_hash |
| email.send.sent | Success | step_id, to_domain, subject_hash, body_hash |
| email.send.failed | Failure | step_id, to_domain, error |

**No recipient address, subject, or body text in audit or logs.**

---

## Failure Modes & Retry Policy

| Failure | Retry | Error Code |
|---------|-------|------------|
| Connection timeout | Yes (max 2 retries) | email_failed |
| SMTP 4xx auth/config | No | email_failed |
| SMTP 421/450/451/452 (temp) | Yes (max 2 retries) | email_failed |
| Other SMTP error | No | email_failed |

- **Timeout:** 30s per attempt  
- **Backoff:** 2s × attempt number between retries  
- **Total attempts:** 3 (initial + 2 retries)

---

## Observability

Logs: request_id, org_id, run_id, step_id, status, latency_ms, provider_name (smtp).  
Never log: email addresses, subject, body, tokens, passwords.
