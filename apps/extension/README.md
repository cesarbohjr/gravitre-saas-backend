# Gravitre Chrome extension

- **Popup:** workspace, approvals waiting, Enrich this page, Ask about this page, connected apps.
- **Side panel:** Ask (about the active tab, continues on gravitre.app), Approvals (approve, or reject with a reason), Activity.
- **Overlay:** enrichment on LinkedIn, Gmail, Outlook, Salesforce, Slack and company sites (activeTab). Writes use the same catalog + Module A path as the web app.

The extension holds its own renewable session (minted by `/extension/connect` through `POST /api/auth/companion-session`, renewed with `/api/auth/companion-refresh`). `ui.css` / `ui.js` carry the same tokens and components as the desktop app.

## Develop

1. Ensure backend includes `/api/extension/*` and web has `/extension/connect`.
2. Chrome → `chrome://extensions` → Developer mode → **Load unpacked** → this folder.
3. Click the extension → **Connect Gravitre** → authorize with your logged-in org.
4. Open a LinkedIn `/in/...` profile (overlay opens) or use **Enrich this page**.

## Permissions

See `manifest.json` and `docs/delivery/browser-extension-v1-2026-08-02.md`.
