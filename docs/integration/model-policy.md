# Org model allowlist policy (STA-90)

Enterprise admins restrict which LLM providers and models agents may use.

## Storage

`organizations.settings.modelPolicy`:

```json
{
  "mode": "open",
  "providers": [],
  "models": []
}
```

Modes: `open` (default), `allowlist`, `blocklist`.

## API

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/settings/model-policy` | Read policy |
| PUT | `/api/settings/model-policy` | Admin update |

## Enforcement

`ModelRouter.complete()` loads org policy and raises `AIModelPolicyError` before provider calls when a model is blocked.
