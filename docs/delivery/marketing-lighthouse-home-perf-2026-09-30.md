# Marketing Lighthouse home performance (not voice acceptance)

Recorded: 2026-09-30

## Finding

Merge-commit Marketing Lighthouse CI
[36672116500](https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/36672116500)
on `3ac840ff27609673a9a876c40d8ea202728b9d6d`:

- URL: `http://127.0.0.1:3000/`
- Assertion: `categories.performance` `minScore` >= `0.75`
- Median found: `0.73`
- All values: `0.53`, `0.73`, `0.73`
- Reports:
  - home: https://storage.googleapis.com/lighthouse-infrastructure.appspot.com/reports/1790745263469-39804.report.html
  - pricing: https://storage.googleapis.com/lighthouse-infrastructure.appspot.com/reports/1790745263854-25662.report.html

PR #224 branch SHA `03dbfaaf` Marketing Lighthouse was PASS. Exact-head required
CI on the merge commit (Web / pytest / voice gate / Integration Smoke) was
SUCCESS.

## Disposition

- Separate production-quality workstream.
- Do not change marketing/frontend performance code as part of voice physical
  acceptance unless it directly prevents the Talk test (it does not).
- Recurring class: home score has previously failed the same `>=0.75` gate
  (see `docs/delivery/perf-reliability-db-audit-2026-08-05.md` B1).
