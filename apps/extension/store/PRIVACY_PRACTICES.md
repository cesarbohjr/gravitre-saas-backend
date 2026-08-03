# Chrome Web Store — Privacy practices answers (Gravitree)

Use these on the **Privacy** tab when creating the item.

## Single purpose

Help operators enrich supported web pages and approve governed Gravitree catalog writes (same org session, approvals, and Outcomes as the web app).

## Permission justifications

| Permission / host | Justification |
|-------------------|---------------|
| `storage` | Persist access token + org id after `/extension/connect` |
| `activeTab` | Inject company-site overlay only when the user invokes Enrich |
| `scripting` | Inject overlay UI on allowlisted / active-tab pages |
| `sidePanel` | Optional side panel UI |
| `linkedin.com` / `www.linkedin.com` | Read visible profile context for catalog enrich |
| `mail.google.com` | Read visible message/context for enrich |
| `outlook.office.com` / `outlook.live.com` / `outlook.office365.com` | Same for Outlook web |
| `*.lightning.force.com` / `*.salesforce.com` / `*.force.com` | Salesforce web page context |
| `app.slack.com` | Slack web page context |
| `gravitre.app` / API hosts | Auth handoff + API calls to Gravitree backend |

**Not used:** `debugger`, `<all_urls>`, webRequest blocking, remote code.

## Data use

- **Personally identifiable information:** Yes — page context may include name, email, title, company when visible on the page; sent to Gravitree API for enrich/actions only.
- **Authentication:** Yes — session JWT stored in extension `chrome.storage.local` after connect.
- **Website content:** Yes — visible page fields extracted for enrich; not used to train third-party models outside Gravitree’s product path.
- **Remote code:** No.

## Certifications

- [x] I do not sell personal or sensitive user data
- [x] I do not use remote code
- Purpose is limited to the single purpose above

## Privacy policy URL

https://gravitre.app/privacy
