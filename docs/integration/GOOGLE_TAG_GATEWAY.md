# Google Tag Gateway (manual) — marketing GTM

First-party measurement path for container `GTM-P9TXQF82` on `gravitre.app`.

Implements Google’s [manual Tag Gateway setup](https://developers.google.com/tag-platform/tag-manager/gateway/setup-guide?setup=manual) using a Next.js edge proxy (Vercel; “Other” CDN pattern). Path `/metrics` is reserved by the product Metrics app, so the gateway uses **`/gtg`**.

| Item | Value |
| --- | --- |
| Container | `GTM-P9TXQF82` |
| Serving path | `/gtg` |
| FPS origin | `gtm-p9txqf82.fps.goog` |
| Proxy | `apps/web/app/gtg/[[...path]]/route.ts` |
| Public path | `/gtg` allowlisted in `apps/web/proxy.ts` (auth middleware) |
| Snippet | `apps/web/components/marketing/google-tag-manager.tsx` |

## Post-deploy verification

1. **Routing:** open `https://gravitre.app/gtg/healthy` — response body should be `ok`.
2. **Geo headers:** open `https://gravitre.app/gtg?validate_geo=healthy` (no trailing slash — Next redirects `/gtg/` → `/gtg`) — response body should be `ok`. Prefer `curl.exe -sS "https://gravitre.app/gtg?validate_geo=healthy"`.
3. **Tag Assistant:** preview the container, browse marketing pages, and confirm Hits Sent use `/gtg` (not `googletagmanager.com`).

## Notes

- Consent Mode defaults still run before the GTM loader; only the script/`ns.html` URLs are first-party.
- Configure each GTM tag’s Consent Settings in the container UI so tags honor Consent Mode.
