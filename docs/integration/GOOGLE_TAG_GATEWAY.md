# Google Tag Gateway (manual) — marketing GTM

First-party measurement path for container `GTM-P9TXQF82` on `gravitre.app`.

Implements Google’s [manual Tag Gateway setup](https://developers.google.com/tag-platform/tag-manager/gateway/setup-guide?setup=manual) using a Next.js edge proxy (Vercel; “Other” CDN pattern). Path `/metrics` is reserved by the product Metrics app, so the gateway uses **`/gtg`**.

| Item | Value |
| --- | --- |
| Container | `GTM-P9TXQF82` |
| Serving path | `/gtg` |
| FPS origin | `gtm-p9txqf82.fps.goog` |
| Proxy | `apps/web/app/gtg/route.ts` + `apps/web/app/gtg/[...path]/route.ts` |
| Public path | `/gtg` allowlisted in `apps/web/proxy.ts` (auth middleware) |
| Snippet | `apps/web/components/marketing/google-tag-manager.tsx` (loads from `googletagmanager.com`; `/gtg` proxy remains available) |

## Post-deploy verification

1. **Routing:** open `https://gravitre.app/gtg/healthy` — response body should be `ok`.
2. **Geo headers:** open `https://gravitre.app/gtg?validate_geo=healthy` (no trailing slash — Next redirects `/gtg/` → `/gtg`) — response body should be `ok`. Prefer `curl.exe -sS "https://gravitre.app/gtg?validate_geo=healthy"`.
3. **Tag install:** view source / Network on a marketing page and confirm `gtm.js?id=GTM-P9TXQF82` loads from `www.googletagmanager.com`.
4. **GA4:** Admin → Data streams → Gravitre should leave “Data collection isn't active” after real traffic (and consent grant where the banner applies).

## Notes

- Consent Mode defaults still run before the GTM loader.
- Configure each GTM tag’s Consent Settings in the container UI so tags honor Consent Mode.
- The `/gtg` Tag Gateway proxy stays deployed for a future first-party switch; the live snippet currently uses Google’s hosted loader so GA4/Tag Assistant install checks pass under CSP.
