# Marketing Consent Mode (Advanced)

Custom consent banner + Google Consent Mode v2 for marketing pages (`apps/web`).

| Item | Location |
| --- | --- |
| Defaults + GTM bootstrap | `apps/web/components/marketing/google-tag-manager.tsx` |
| Banner UI | `apps/web/components/marketing/marketing-consent-banner.tsx` |
| Helpers | `apps/web/lib/marketing-consent.ts` |
| Container | `GTM-P9TXQF82` |

Follows [Troubleshoot consent mode](https://support.google.com/tagmanager/answer/14522438#issues) and [Consent Mode (Advanced)](https://developers.google.com/tag-platform/security/guides/consent?consentmode=advanced).

## Issue checklist (Tag Assistant)

| Tag Assistant / Help Center issue | How we address it |
| --- | --- |
| Consent tab empty | Consent defaults + `gtag` stub run in a **blocking inline** script before `gtm.js`; CSP allows `googletagmanager.com`. |
| Default consent not set | All four v2 params set: `ad_storage`, `ad_user_data`, `ad_personalization`, `analytics_storage`. |
| Default consent set too late | Defaults are **not** deferred via `next/script` `afterInteractive`; they run synchronously ahead of the GTM loader. |
| Consent doesn't update | Banner calls `gtag('consent','update', …)` via a stub that pushes the `Arguments` object (not a plain array). |
| Consent doesn't adapt to regional settings | EEA/UK/CH defaults are `denied` with `region: […]`; all other regions default to `granted`. |

## Verify

1. Tag Assistant → Consent tab shows defaults before/with container load.
2. Accept / reject on the banner updates Consent tab parameters.
3. In a banner region with no prior choice, analytics stays denied until Accept.
