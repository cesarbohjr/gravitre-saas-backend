# PR 611: exact-head CI and bounded DEC-008 reader reproduction

Verified 2026-11-22 against `9b136df947a05bac56d7ec20b240e3f904ea8cf5`.
PR 611 remained open on `feat/master-qa-tranche27-orchestration` at this head.
No publication, merge, deployment, migration, provider write or live dispatch occurred.
All 43 findings remain uncertified. Existing signed QA evidence is preserved.

## Hosted CI

All ten exact-head PR workflows completed successfully:

| Workflow | Run |
| --- | --- |
| Core | https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/45051919766 |
| Operations | https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/45051919749 |
| QA04 governed execution | https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/45051919882 |
| QA12 independent acceptance | https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/45051919746 |
| Identity | https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/45051919720 |
| Data | https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/45051919739 |
| Intelligence | https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/45051919836 |
| Voice | https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/45051919870 |
| Browser | https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/45051919722 |
| Marketing | https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/45051919762 |

All five required Core contexts succeeded:

| Context | Job |
| --- | --- |
| Backend (pytest) | https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/45051919766/job/137298749996 |
| Web (lint + typecheck + build) | https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/45051919766/job/137298750034 |
| Shared runtime text/voice gate | https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/45051919766/job/137298749992 |
| Dependency audit | https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/45051919766/job/137298750132 |
| Integration Smoke Test | https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/45051919766/job/137298750114 |

Backend log at 2026-11-22T19:06:40Z reports **17,407 passed, 44 skipped,
215 warnings, 14 subtests passed in 3694.26s** for the full pytest step.
The entire Backend job, including subsequent gates, succeeded.

QA12's retry succeeded after the diagnosed runner setup cancellation. Physical voice
job 137303837413 ran 49 offline tests and 20 additional offline tests (6 deselected),
then explicitly printed that physical microphone/speaker and natural full-duplex
usability acceptance remain NOT RUN. This is not physical-device acceptance.
Live provider, signed QA dispatch, controlled contact write, isolated billing
Playwright, production proof and other dispatch-only jobs were skipped. Core's
Billing E2E was skipped. These skips are not verified live/provider/billing acceptance.
Real isolated PostgreSQL jobs that ran in these workflows do not validate this new
reader reproduction against PostgreSQL.

## Local reproduction

Clean detached worktree was created at the verified SHA, preserving other worktrees.
Read AGENTS.md, engineering standards, applicable cursor rules and DEC-008 in
`master-qa-remediation-register.v2.json` before adding the unpublished test file:
`backend/tests/test_audit_reader_dec008_reproduction.py`.

Command, from the isolated worktree's backend directory:

```sh
/workspace/scratch/cfe2eca38c2b/qa-venv/bin/python -m pytest tests/test_audit_reader_dec008_reproduction.py -q --tb=short
```

**Result: 5 failed, 8 passed, 2 warnings in 3.48s.** Normal backend conftest loaded.
The production reader and Supabase SDK executed unchanged. Only the HTTP transport
was isolated with httpx.MockTransport; its relational oracle applies predicates
actually present in SDK requests. No remote connection or credentials were used.
This is source/transport reproduction, not database, RLS, caller or deployed proof.
No local PostgreSQL installation (`/usr/lib/postgresql` or psql) was available.

### Confirmed equal-timestamp loss

Seven org-A records were sorted newest-first by (created_at, id):
IDs 90 at 12:00:01, IDs 15,14,13,12,11 at 12:00:00, and ID 1 at 11:59:59 UTC,
all on 2026-11-22. IDs are UUIDs constructed from those integer suffixes.
Org-B records were interleaved at newer and equal timestamps. Page size was 2.

Expected pages: `[90,15]`, `[14,13]`, `[12,11]`, `[1]`.
Actual pages: `[90,15]`, `[1]`.
Four valid org-A records (14,13,12,11) were lost.

The cursor correctly encodes and decodes both timestamp and ID, but
`query_audit_log` discards the ID (`cursor_created_at, _ = decoded`) and emits only
`created_at=lt.<boundary>`. All remaining equal-timestamp rows are excluded.
Its ordering is correctly two-column; its seek predicate is not.

### Boundary and parser results

- Tenant-scoped multi-page traversal over distinct timestamps: passed.
- Interleaved other-tenant rows and foreign-row cursor: no tenant leakage observed;
  every SDK request retained `org_id=eq.<requested org>`. This is not RLS proof.
- Inclusive start/end timestamp boundaries: passed.
- Cursor round-trip retaining ID: passed.
- Three malformed/missing-field cursor strings: safely resumed the first scoped
  page, with no tenant leakage observed.
- Valid base64 JSON containing array, null, number or string: four failures,
  `AttributeError` at `data.get("created_at")`. The parser assumes an object and
  does not catch AttributeError. Repair should type-check the decoded JSON object.
- The sibling `query_audit_events` RPC reader passes both timestamp and ID and
  org restriction: payload contract passed. Its retained SQL migration uses
  `(e.created_at,e.id) < (p_cursor_created_at,p_cursor_id)`. No RPC SQL executed here.

There is no automatic table/RPC fallback inside this module. Invalid-cursor
fallback is the scoped first-page path; non-object JSON currently escapes it.
Source search found `query_audit_events` imported by context_packs; it found no
other app call site for `query_audit_log`. Customer reachability therefore remains
unproven, and this result does not establish audit_logs/audit_events consumer parity.

## State and next engineering action

CI reconciliation is verified on the exact head. DEC-008 now has a confirmed local
reader defect and additional parser boundary defect, with unpublished failing
tests. No source repair or finding certification is claimed. Both audit stores,
all 12 installed workflows, both-parent reconciliation, owner/main-only signed
fixture guards and completed signed QA pass 44863581946 remain untouched.

Next: repair the reader's lexicographic (created_at,id) cursor predicate and
non-object cursor parsing while retaining org scoping, then make these exact
assertions pass and validate the reader against disposable PostgreSQL before
publication and exact-head hosted CI.
