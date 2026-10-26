# Gravitre Chrome extension

- **Popup:** signed in (Ask box, On this page, approvals waiting, connected apps, What Gravitre can see), signed out, session expired, no workspace access and offline (last saved snapshot).
- **Side panel:** Ask (page context, suggested Plays, plans that wait for approval, sources, `/` commands, `@` agents, selection, voice), Approvals (field changes, reject with a reason, undo, J/K/A/R), Activity (recent assignments), Settings and first-run consent.
- **On the page:** a draggable floating button (Alt+G opens the side panel), an "In CRM" chip and a card next to the person or company. Built-in sites are LinkedIn, Gmail, Outlook, Salesforce and Slack; people can add more from Settings (optional host permission). Nothing is read on a site the person turned off, and form fields are never read.

The extension holds its own renewable session (minted by `/extension/connect` through `POST /api/auth/companion-session`, renewed with `/api/auth/companion-refresh`). `ui.css` / `ui.js` carry the same tokens and components as the desktop app. `providers.js` (vendor logo lookup) is generated from the web provider registry by `scripts/package-extension-chrome-store.py`; the logo files load from gravitre.app.

## Develop

1. Ensure backend includes `/api/extension/*` and web has `/extension/connect`.
2. Chrome → `chrome://extensions` → Developer mode → **Load unpacked** → this folder.
3. Click the extension → **Connect Gravitre** → authorize with your logged-in org.
4. Open the side panel, review "Before you start", then open a LinkedIn `/in/...` profile.

## Permissions

See `manifest.json` and `docs/delivery/browser-extension-v1-2026-08-02.md`.
