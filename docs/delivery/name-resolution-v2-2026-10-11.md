# Name resolution v2: stronger Gmail lookup, one contract for people, records, lists and files (2026-10-11)

Base: `main` at `a7719cba` (PR #357). Paths are relative to `backend/`. Every mailbox, person, address and file in the tests and measurements below is an invented fixture (`.example` domains); no real account, Railway or production system was read.

## What changed

### Gmail recipient lookup (`app/services/recipient_resolution.py`)

- **Which account is searched.** The Gmail account the user named in the request (by its address, e.g. "from steph.lane@home.example"); otherwise the account a send goes from by default: the most recently updated usable `connectors` row, the same one `get_connector_by_type` picks. Only that one account is searched. Every list and header read carries its `connector_id`, every candidate records `account` (row id), `account_label` and `account_stamp` (the row's `updated_at`), and the chosen candidate pins `connector_id` on the staged send, so the address book searched and the sending account are always the same. Searching all connected accounts was rejected as the default: it would offer people from one mailbox and then send from another.
- **Precise query.** `(from:X OR to:X OR cc:X) -category:promotions -category:social`, with X quoted when it has two words ("Stephanie Khan" is a phrase).
- **Bounded pagination.** Pages of 25 ids (`PAGE_SIZE`), up to 3 pages (`MAX_PAGES`) and 60 messages whose headers are read (`MAX_MESSAGES`), all inside a 4 s budget (`LOOKUP_BUDGET_S`; a hard stop at 5.5 s). Header reads run six at a time and only fetch From, To, Cc, Date and the list headers (`format=metadata`), never bodies. `gmail.list_messages` and its executor now pass `page_token` / `label_ids` through (the catalog already declared `page_token`).
- **Statuses.** `resolved` / `ambiguous` / `not_found` / `incomplete` / `unavailable`:
  - `incomplete` when a cap, the time budget, or a failed page stops the search before the matches run out. It is never treated as unique: one candidate gets "I found Stephanie Khan (stephanie.khan@acme.example), but I couldn't check all of your mail, so there may be another Stephanie. Is that who you mean?"; none gets "I couldn't find Jordan in the part of your Gmail I could check...".
  - `unavailable` carries a reason: `not_connected`, `permission` (auth expired, permission denied, missing scope), `rate_limited`, `error`, `time_budget`. With a lookup attempted, the reply says so ("I don't have permission to read your Gmail right now (it may need reconnecting), so I can't look up Stephanie. What's the email address?") and any model-written address is dropped.
- **Noise.** Never offered, and counted in `coverage.excluded`: the user's own addresses (From of SENT/DRAFT messages, plus the account's configured address), no-reply and role senders (`*-noreply`, `notifications@`, `newsletter@`, ...), list relays ("Stephanie Khan via Acme Team"), and addresses seen only on bulk mail (List-Unsubscribe, List-Id, `Precedence: bulk`, Auto-Submitted, or the promotions/social/forums/updates categories). People the user wrote to rank first.
- **Drafts.** The real connector has `gmail.drafts.create` but no drafts listing. A draft is only seen when `messages.list` returns a DRAFT-labelled message that matches the query, so draft coverage is incidental and is not claimed (`coverage.drafts = "incidental"`). An address seen only in a draft is never resolved on its own: "The only Stephanie Park I found is spark@initech.example, and only in an unsent draft, so I can't confirm it. Should I use that address?" A draft is never treated as proof that anything was sent.
- **Freshness and revalidation.** Cached candidates (`recipient_candidates`) carry `resolved_at` and the account stamp. Before a reply picks from them they are looked up again if older than 15 minutes (`CANDIDATE_TTL_S`), if the account row was removed or reconnected (`updated_at` changed), and a read that fails for permission reasons clears them and asks for the address.
- **Choosing.** Besides surnames, ordinals, full names, domains and addresses, a single offered candidate can be confirmed with "yes" / "that's her".

### One contract for every source (`app/services/object_resolution.py`)

`ResolutionCandidate` (aliased as `RecipientCandidate`) keeps `name`, `address`, `source`, `account`, `account_label`, `account_stamp`, `object_type` (`person`, `contact`, `list`, `segment`, `file`), `object_id`, `access` (`ok` after a successful read for that account, `denied`, `unknown`), `resolved_at` and `evidence`. `Resolution` (aliased as `RecipientResolution`) adds `status`, `reason`, `coverage`, `accounts`, `calls` and `latency_ms`. One `decide()` rule turns candidates into a status for every source, so chat and voice (and every resolver) say the same thing. Old stored candidates still load (missing fields default; no freshness stamp means stale).

Resolvers, each built only on read actions that already exist in `tool_service`:

| Resolver | Read actions | Coverage rule |
|---|---|---|
| Outlook participants (`resolve_outlook_participant`) | `microsoft365.users.get` (own address), `microsoft365.mail.messages.list` with a new `search` parameter (`$search="participants:<name>"`; `$orderby` dropped because Graph refuses both) | `@odata.nextLink` present means incomplete |
| CRM contacts (`resolve_crm_contact`) | `hubspot.contacts.search` (query on email/first/last/company, filtered here by name), `salesforce.contacts.search` (`name`) | HubSpot `total` above rows returned, or Salesforce `done=false` / `totalSize` above rows, means incomplete |
| Lists and segments (`resolve_list`) | `apollo.lists.list`, `constant_contact.contact_lists.list`, `constant_contact.segments.list` (names matched here) | Constant Contact `_links.next` means incomplete; an exact name match resolves among partial ones |
| Files (`resolve_file`, `verify_file_access`) | `google_drive.search_files` / `microsoft365.search_files`, then `google_drive.get_file_metadata` / `microsoft365.get_file_metadata` for the chosen file, with the account it was found in | A full page (25 hits) means incomplete; title must match (content-only hits are dropped) and a type word ("spreadsheet", "deck", "pdf") filters by MIME type or extension |

The Outlook resolver is wired into the same email grounding for `microsoft365.mail.send`; the others are callable resolvers with unit tests and are not yet wired into a conversation flow except files (below).

### "Send Stephanie the budget spreadsheet"

- The recipient and the file are resolved independently in the same turn (`ground_email_recipient` → `_ground_file`). `extract_recipient_name` now also reads "send Stephanie the ..."; `extract_file_request` reads "the budget spreadsheet" only when a file word is present.
- One question per ambiguity, one per turn: an open recipient question goes first and the file question waits for the next reply ("Got it, Stephanie Khan. I found two files that match "budget spreadsheet": Budget 2026 (in Finance, modified Oct 3, 2026) and Budget 2026 (in Drafts, modified Sep 12, 2026). Which one?"). Same-named files are told apart by folder, date and source.
- Before the file is attached to the draft, a metadata read for that account must succeed; it is read again before the approval prompt when the last check is older than 5 minutes (`FILE_VERIFY_TTL_S`). The staged write carries `file_id`, `file_source`, `file_account`, `file_name`, `file_link`: the id, not just the title. These args are part of the approval binding digest.
- **Attachments are not supported by the existing send actions** (`gmail.messages.send` builds a plain-text MIME message; `microsoft365.mail.send` sends `sendMail` without attachments). Nothing pretends otherwise: the user is told "I can't attach files to emails from here yet, so I'll add a link to it; the recipient needs access to open it.", the approval prompt shows "File: Budget 2026 on Google Drive, added as a link (attachments aren't supported yet)", and the executors append `Budget 2026: <link>` to the body (`body_with_file_link`). Sharing is not changed.
- Right before an approved send runs, `revalidate_bound_targets` (called in `ChatConnectorExecutionService._execute_plan` after `assert_plan_matches_binding`, before write preflight compiles) reads the file's metadata again; if it no longer opens, nothing is sent: "I can't open Budget 2026 with your Google Drive account anymore, so I didn't send the email. Nothing was sent."
- No file source connected: "I can't search your files from here yet, so I can't include it. Connect Google Drive or OneDrive to do that." The email continues without it.

### A path that skipped grounding

The live unified turn (`apply_unified_turn_live`, `unified_turn_reasoning_service.py`) staged Gmail sends without the recipient lookup. When the send tool was only offered by name (the model first loads its schema, then calls it), the model's invented address was sealed into the ledger and could be approved and sent (reproduced in the harness: a send to `stephanie@invented.example`). That path now calls the same `ground_email_recipient` / `apply_resolution_to_stage` before the arguments are sealed, and passes the same approval notice. There is still one approval path: the grounding only changes the args before staging.

## Capability table

"Supported" = resolver in this change with tests. "Proposed" = a read action exists but no resolver yet. "Unavailable" = Gravitre says "I can't search X yet" (`cant_search_yet`).

| Object | Source | State | Read actions / reason |
|---|---|---|---|
| Email participants | Gmail | Supported, wired to `gmail.messages.send` | `gmail.messages.list` + `gmail.messages.get` (metadata) |
| Email participants | Outlook | Supported, wired to `microsoft365.mail.send` | `microsoft365.mail.messages.list` (`$search`) + `microsoft365.users.get` |
| Gmail drafts | Gmail | Unavailable (incidental only) | no drafts listing in the connector |
| People directory / contacts | Gmail, Outlook | Unavailable | no People API or Outlook contacts read wired |
| Contacts | HubSpot | Supported (resolver) | `hubspot.contacts.search` |
| Contacts | Salesforce | Supported (resolver) | `salesforce.contacts.search` |
| Contacts | Pipedrive, Apollo, Intercom, EngageBay, Clio | Proposed | `*.persons.search` / `*.contacts.search` exist |
| Lists | Apollo | Supported (resolver) | `apollo.lists.list` |
| Lists | Constant Contact | Supported (resolver) | `constant_contact.contact_lists.list` |
| Segments | Constant Contact | Supported (resolver) | `constant_contact.segments.list` |
| Lists | HubSpot | Unavailable | only `hubspot.lists.get` by id; no list search |
| Segments | HubSpot | Unavailable | no segment read |
| Lists | Mailchimp | Unavailable | `mailchimp.audiences.list` path not verified (audit: likely wrong) |
| Lists | Klaviyo | Unavailable | not integrated |
| Lists | Marketo | Proposed | `marketo.lists.get_leads` reads members by id only |
| Files | Google Drive | Supported, wired to email sends | `google_drive.search_files` + `google_drive.get_file_metadata` |
| Files | OneDrive | Supported, wired to email sends | `microsoft365.search_files` + `microsoft365.get_file_metadata` |
| Files | Notion, Confluence, Slack | Proposed | `*.search_files` / `*.get_file_metadata` exist |
| Files | Dropbox | Unavailable | not integrated |
| Attachments on sends | Gmail, Outlook | Unavailable | sends carry a link instead |

## Measurements

Scenario harness, fake connectors at the executor seam (preflight, sealed reads, approvals and the write gate are real). Script: `python -m tests.scenarios.measure_name_resolution` (from `backend/`).

### Gmail lookup accuracy

13 of 13 fixture cases correct, both with no latency and with 150 ms per simulated read.

| Mailbox | Query | Expected | Got | Reads | ms at 150 ms/read |
|---|---|---|---|---|---|
| noisy | Stephanie | ambiguous (Wu, Khan at acme, Khan at gmail, Park) | ambiguous | 16 | 627 |
| noisy | Stephanie Wu | resolved | resolved | 5 | 314 |
| noisy | Stephanie Khan | ambiguous (same person, two addresses) | ambiguous | 6 | 314 |
| noisy | Stephanie Park | ambiguous (draft only, confirm) | ambiguous | 2 | 309 |
| noisy | Stephanie Rivera | not_found (newsletter sender only) | not_found | 2 | 310 |
| noisy | Stephanie Moreau | not_found (only inside a forward) | not_found | 1 | 158 |
| noisy | Stephanie Lane | not_found (the user herself) | not_found | 15 | 618 |
| noisy | Wu | resolved | resolved | 5 | 314 |
| noisy | Pat | resolved | resolved | 5 | 312 |
| noisy | Jordan | not_found | not_found | 1 | 157 |
| busy, 82 hits | Stephanie | incomplete (Khan only seen; Wu beyond the cap) | incomplete | 63 | 2010 |
| busy, 82 hits | Stephanie Wu | resolved | resolved | 2 | 309 |
| busy, 42 hits | Stephanie | ambiguous (second page reached) | ambiguous | 44 | 1386 |

Median 314 ms, worst 2.0 s (3 list pages + 60 header reads) at 150 ms per read, inside the 4 s budget. The noisy mailbox has 16 messages: two Stephanies (one with a work and a personal address), a draft-only Stephanie, a promotions newsletter, a marketing sender left in the inbox, two no-reply senders using a Stephanie's name, a mailing-list relay, the user (also a Stephanie) mailing herself, and forwarded mail.

### File lookup accuracy

6 of 6: two same-named sheets (ambiguous), one sheet (resolved), "budget doc" picks the document not the sheet, a content-only match is not offered, no such file (not found), no file source connected (unavailable). One search read per lookup; one metadata read per chosen file.

### Conversations (text and voice, identical results)

| Flow | Turns to approval | Clarifying questions | Right recipient | Connector reads |
|---|---|---|---|---|
| one Stephanie | 3 | 0 | yes | 3 |
| noisy mailbox, pick Wu | 4 | 1 | yes | 16 |
| budget sheet, two same-named files | 4 | 1 | yes | 5 |
| budget sheet, two Stephanies and two files | 5 | 2 (one per ambiguity) | yes | 6 |

No flow asks the same question twice. Every flow reaches a single approval prompt, and the scenario tests check that the send carries the chosen address and file id, and that a lost file blocks the send.

## Tests

- `tests/scenarios/test_name_resolution_v2_scenarios.py` (40): noisy-mailbox table, noise counting, the phrase query, pagination, the page cap, the time budget, no-match-with-pages-left, permission failure, default and named account selection, and on text and voice: the noisy conversation, stale and reconnected-account revalidation, permission failure clearing cached candidates, the budget-spreadsheet flow end to end, two ambiguities, one file, an unreadable file, no file source, and file access lost after approval.
- `tests/services/test_object_resolution.py` (44): the contract, freshness, account selection, choosing, the capability table, each resolver (Outlook, HubSpot, Salesforce, Apollo, Constant Contact, files), file access checks, execution-time revalidation, link handling, the connector extensions, and Outlook grounding.
- Existing: `tests/scenarios/test_recipient_resolution_scenarios.py` unchanged and passing.

## Uncertainties

- Not run against real Gmail, Graph, Drive, HubSpot, Salesforce, Apollo or Constant Contact. The fakes follow the documented response shapes, but real ranking, real `nextPageToken` behaviour and real category labels may differ.
- Graph `$search` with KQL `participants:` on messages is assumed from Microsoft's documentation; it could not be tried. If it is rejected, the Outlook lookup reports `unavailable` (honest, not wrong). Graph also caps search results; we read one page of 50.
- Gmail category exclusion (`-category:promotions -category:social`) can hide a real person whose mail Gmail filed there; they are only found by a fuller query or a typed address.
- The user's own address is learned from SENT/DRAFT messages and the account config; a mailbox where the user never sent anything matching the name and whose connector row has no `email` in config could still offer the user's own address.
- Drive and OneDrive search executors do not return a next-page token, so "a full page" is the only incomplete signal for files.
- HubSpot's `CONTAINS_TOKEN` search and Salesforce's `LIKE` are matched again here by name; contacts without a name (email only) match on the address local part only.
- The send link is plain text in the body; whether the recipient can open it depends on the file's sharing, which Gravitre does not read (`drive.permissions.list` exists and could be used to warn) and does not change.
- Only one Gmail account is searched per lookup (the named or default one). A user who means someone only present in another connected account gets "not found" for this account and has to name that account or give the address.
