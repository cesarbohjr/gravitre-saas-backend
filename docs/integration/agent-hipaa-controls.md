# HIPAA BAA + PHI controls (STA-110)

Organizations that handle protected health information (PHI) must accept a Business Associate Agreement (BAA), enable HIPAA mode, and use US data residency before PHI-capable connectors or sensitive outbound tools run.

## HIPAA ready

`hipaaReady` is true when all of the following hold:

1. HIPAA mode is **enabled** in org settings
2. Current BAA version is **accepted** (`CURRENT_BAA_VERSION`, stored in `org_hipaa_baa_acceptances`)
3. Organization **data region** is `us`

## Blocked when not HIPAA ready

| Control | Behavior |
|---------|----------|
| PHI-sensitive tool actions | `email.send`, `webhook.post`, `slack.post_message` raise `HIPAA_REQUIRED` |
| PHI-capable connectors | Any tool using a connector with `phi_capable = true` is blocked |

Tag connectors via `PUT /api/enterprise/connectors/{id}/phi` or `PATCH /api/connectors/{id}` with `phiCapable`.

## API

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/enterprise/hipaa` | Status: BAA, region, PHI connector count, blocked actions |
| POST | `/api/enterprise/hipaa/accept-baa` | Accept current BAA version |
| PUT | `/api/enterprise/hipaa` | Enable or disable HIPAA mode |
| PUT | `/api/enterprise/connectors/{id}/phi` | Tag connector as PHI-capable |

## Audit

- `enterprise.hipaa.baa_accepted`
- `enterprise.hipaa.enabled` / `enterprise.hipaa.disabled`
- `connector.phi_capable.updated`

## Related

- STA-80 data residency — US region required for HIPAA mode
- STA-82 PII redaction — complements PHI handling in logs and exports
- STA-113 healthcare vertical pack — builds on these controls
