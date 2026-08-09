# CWS first publish checklist (Gravitre)

First-time publish **cannot** be completed by API alone: Google requires Store listing + Privacy tabs filled in the Developer Dashboard, then Submit for review.

## Package

- Zip: `apps/extension/dist/gravitre-extension-chrome.zip`
- Rebuild: `python scripts/package-extension-chrome-store.py`
- Manifest version: `0.5.0` (MV3)

## Dashboard steps

1. Sign in: https://chrome.google.com/webstore/devconsole (account with 2FA).
2. Pay one-time developer registration if prompted.
3. **Add new item** → upload the zip.
4. **Store listing** — copy from `LISTING.md` (name, summary, description, category Productivity).
5. **Privacy** — copy from `PRIVACY_PRACTICES.md`.
6. Upload icons (use `apps/extension/icons/icon128.png` as store icon; provide 1280×800 or 640×400 screenshots when available).
7. Visibility: **Unlisted** (beta) or **Public**.
8. **Submit for review** (optionally defer publish until after review).

## After Google accepts

Listing URL shape:

`https://chromewebstore.google.com/detail/gravitre/<EXTENSION_ID>`

1. Set Vercel env `NEXT_PUBLIC_CHROME_WEB_STORE_URL` to that URL (Production + Preview as needed).
2. Redeploy `apps/web`.
3. Confirm `/features/extension` CTA reads **Install from Chrome Web Store** and the link resolves.

## API updates (later)

After the first manual publish, note `PUBLISHER_ID` + `EXTENSION_ID` for Chrome Web Store API v2 upload/publish of future versions.
