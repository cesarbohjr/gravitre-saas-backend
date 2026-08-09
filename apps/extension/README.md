# Gravitre Chrome extension (v1)

Overlay-and-approve enrichment on LinkedIn, Gmail, Outlook, and company sites (activeTab). Writes use the same catalog + Module A path as the web app.

## Develop

1. Ensure backend includes `/api/extension/*` and web has `/extension/connect`.
2. Chrome → `chrome://extensions` → Developer mode → **Load unpacked** → this folder.
3. Click the extension → **Connect Gravitre** → authorize with your logged-in org.
4. Open a LinkedIn `/in/...` profile (overlay opens) or use **Enrich this page**.

## Permissions

See `manifest.json` and `docs/delivery/browser-extension-v1-2026-08-02.md`.
