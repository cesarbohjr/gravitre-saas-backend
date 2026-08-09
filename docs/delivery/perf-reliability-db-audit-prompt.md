# Performance / reliability / database audit prompt

Source: consolidated Full QA + System Optimization Sweep (prior program prompt).

Context for this run (2026-08-05): G.5 routing/schema work CLOSED on tip ~`40064803` / `ce6db384`; full CI green. This audit is the next coverage gap — page load times, broken links / dead buttons, and the Supabase query/indexing layer.

Standing gates unchanged: live evidence for every claim; findings report before fixes; local pytest green ≠ prod-fixed.

---

## Cursor Prompt — Full QA and System Optimization Sweep

GOAL
Run a comprehensive QA and performance audit across Gravitre's entire
web platform (marketing site + app) and backend, covering functional
correctness, performance, and code hygiene. This is an AUDIT — findings
first, fixes batched and reviewed, not a blind "fix everything you find"
pass. Same standing gates as everything else in this program: live
evidence for every claim, no "should be fine" without a real check.

═══════════════════════════════════════════════════
PART A — Link and navigation integrity (real browser, not code-read)
═══════════════════════════════════════════════════
Reuse/extend the existing Playwright-based crawler from the earlier nav
audit if it still exists; build it if not.
1. Crawl every internal link, nav item, footer link, and in-app CTA on
   both the marketing site and the authenticated app, using REAL browser
   clicks (not just HTTP fetches) — this is the only way to catch
   client-side routing/hydration failures, not just dead routes.
2. For each: confirm the click actually navigates, the destination has
   real content (not an empty/stub page), HTTP status isn't 4xx/5xx, and
   no console errors fire during navigation.
3. Specifically re-check the known-fragile patterns from earlier in this
   program: hub pages whose "card grid" links to detail pages that don't
   exist (the /support, /guides pattern found before), and result_url
   links in chat/canvas completion cards actually resolving to real
   external records, not dead or misleading destinations.
4. Report every broken link/button found, source page, and failure type.

═══════════════════════════════════════════════════
PART B — Performance audit
═══════════════════════════════════════════════════
1. Run Lighthouse (or equivalent) against the marketing site's key pages
   (home, pricing, docs, blog) and the app's main authenticated views
   (chat, dashboard, marketplace, settings). Report Core Web Vitals:
   LCP, CLS, INP/FID, TTFB.
2. Identify render-blocking resources, unoptimized images, unused
   JS/CSS bundles, and any page shipping noticeably more JS than its
   content requires.
3. Check API response times for the endpoints the chat UI depends on
   most heavily (connector status, catalog reads, notification polling)
   — flag anything with p95 latency high enough to visibly affect the
   "almost immediate" feel this program has targeted since the
   responsiveness-architecture work.
4. Check for N+1 query patterns or missing indexes on any
   frequently-hit endpoint, especially ones touched by the new pack/
   connector work (intelligence_pack_sources, external_signals,
   audit_events at scale).

═══════════════════════════════════════════════════
PART C — Code and config hygiene
═══════════════════════════════════════════════════
1. Run the full lint suite (whatever's configured — ESLint/Ruff/etc.)
   across the frontend and backend. Report error and warning counts by
   category, don't just report "lint passed/failed" as a binary.
2. Check for JSON schema violations or malformed config anywhere the
   codebase parses JSON at runtime (catalog definitions, workflow
   schemas, connector configs) — a malformed catalog entry should fail
   loudly at build/deploy time, not silently at runtime months later.
3. Check for dead code, unused imports, and orphaned files, especially
   around the connector/pack work where multiple phases have added and
   sometimes superseded earlier scaffolding (e.g. confirm nothing from
   the original Meson/GoalService skeleton work is now dead weight after
   the write-gate unification).
4. Confirm environment variable documentation matches what's actually
   read at runtime — flag any env var referenced in code but undocumented,
   or documented but no longer read.

═══════════════════════════════════════════════════
PART D — CI and test suite health
═══════════════════════════════════════════════════
1. Run the full test suite, report pass/fail/skip counts explicitly —
   per this program's own standing rule, skipped must never be reported
   as passed.
2. Flag any test that's been consistently skipped/flaky for a while
   (the kind of "pre-existing red check" this program has previously
   agreed to scope around rather than block on) — surface it as a
   visible, trending backlog item, not silent permanent noise.
3. Confirm the registration-contract tests (catalog_write_authority
   enumeration, output-verification schema checks, BYO fail-closed
   tests) still pass at their expected counts — these are the load-
   bearing tests for everything else in this program, worth a specific
   check that they haven't quietly regressed.

═══════════════════════════════════════════════════
PART E — Error handling and observability
═══════════════════════════════════════════════════
1. Confirm every user-facing error path (connector failures, validation
   errors, approval-required states) shows the specific, mapped error
   copy this program already built (format_tool_error_for_user, the
   STA-303 error-code split), not a generic fallback — spot-check across
   several connectors, not just the ones recently touched.
2. Confirm notification delivery (bell + email) actually fires for a
   real completed action end-to-end, live, not just code-reviewed.
3. Check for any silent failure mode: an action that reports success
   without producing verifiable output (the exact class of bug this
   program has fixed multiple times) — spot-check a sample across
   connectors outside the ones already verified, since this program's
   own numbers show a real backlog of actions still missing output-
   verification schemas.

═══════════════════════════════════════════════════
PART F — Security/dependency hygiene
═══════════════════════════════════════════════════
1. Run a dependency audit (npm audit / pip-audit or equivalent) across
   frontend and backend, report known CVEs by severity.
2. Confirm no secrets/API keys are committed to the repo or exposed in
   client-side bundles.
3. Confirm rate limiting exists on public-facing endpoints, especially
   anything touching connector OAuth callbacks or webhook receivers.

═══════════════════════════════════════════════════
DELIVERABLE
═══════════════════════════════════════════════════
One consolidated report: findings by category (broken links,
performance regressions, lint/hygiene issues, test health, error-
handling gaps, security items), each with severity and evidence.
Do NOT start fixing anything until this report is reviewed — some
findings may be acceptable-and-known (like existing pre-existing red
checks this program already scoped around), others may be new and
urgent. Prioritize fixes the same way this program always has:
trust-critical and user-facing correctness first, performance second,
pure hygiene/lint last.

Given this program's own numbers (605 wired connector actions, 172 write
actions, 164 still missing output-verification schemas, multiple
in-flight connector batches), Part E's spot-check on output verification
is probably the single highest-value section here, since it's the exact
class of bug that's bitten this program more than once already, and a
blanket QA sweep is a natural moment to sample beyond just the connectors
already under active work.
