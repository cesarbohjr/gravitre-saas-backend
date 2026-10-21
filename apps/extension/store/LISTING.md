# Chrome Web Store listing draft (Gravitre extension)

**Status:** NOT LIVE (checked 2026-10-21). The store page for item id `iegkidilloajngolbpgfkaeglblnklol` says "This item is not available". Check the item's status in the Developer Dashboard and finish the steps in `SUBMISSION_CHECKLIST.md`.

Until the listing is installable, /features/extension shows **Install guide** and a zip download (rolling GitHub release `extension-latest`, built by `.github/workflows/extension-release.yml`).

Once the listing is public or unlisted and approved, set this in Vercel (Production) and redeploy:

`NEXT_PUBLIC_CHROME_WEB_STORE_URL=https://chromewebstore.google.com/detail/gravitre/<EXTENSION_ID>`

Note: Chrome Web Store **Dev Console** URLs (`chrome.google.com/webstore/devconsole/…`) are not customer install links.

## Listing fields

| Field | Value |
|-------|--------|
| Name | Gravitre |
| Summary | Overlay enrich + approve governed CRM writes — same Outcomes as Gravitre chat. |
| Category | Productivity |
| Language | English |

### Description (short)

Gravitre brings your org’s governed catalog to LinkedIn, Gmail, Outlook, and company pages. Enrich from page context, approve writes once, and see them in Outcomes — not a parallel CRM bot and not DOM automation for HubSpot/Apollo.

### Description (detailed)

- Connect with your existing gravitre.app org session
- Enrich LinkedIn profiles, Gmail, Outlook web, and company sites
- Approve catalog writes (Apollo / HubSpot when connected)
- Same approval gate and Outcomes visibility as chat
- Explicit host permissions only — no `<all_urls>`, no debugger

Supported browsers for the public claim: **Chrome, Edge, Brave** (same MV3 pack).  
**Not supported:** Firefox, Safari, mobile.  
Does not automate InMail or click CRM UIs on your behalf. No agentic multi-step form control.

### Privacy

Session token and org id stored locally in extension storage. Page context sent to Gravitre API for enrich/actions only. See https://gravitre.app/privacy

## Package

```bash
python scripts/package-extension-chrome-store.py
```

Upload the zip from `apps/extension/dist/gravitre-extension-chrome.zip` in the Chrome Developer Dashboard.

## Screenshots needed (human)

1. LinkedIn overlay enrich  
2. Approve write confirm  
3. Outcomes entry with `browser_extension`  
4. Popup Connect Gravitre  

Do not use mockups that claim Edge/Brave/Salesforce/Slack/workflows/chat until the matching version’s marketing update has shipped.
