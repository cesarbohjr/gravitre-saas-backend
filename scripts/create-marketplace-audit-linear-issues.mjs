#!/usr/bin/env node
/**
 * Create Gravitre Marketplace audit backlog issues in Linear (June 2026 architecture audit).
 * Idempotent: skips issues whose ref tag already exists in the Gravitre Marketplace project.
 *
 * Usage:
 *   npm run linear:marketplace-audit
 *
 * Auth: LINEAR_API_KEY env OR @schpet/linear-cli keyring (`linear auth login`).
 */

import { spawnSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

function resolveLinearCmd() {
  if (process.env.LINEAR_CLI_BIN) {
    return shQuote(process.env.LINEAR_CLI_BIN);
  }
  const localTool = path.join(
    process.env.LOCALAPPDATA || path.join(os.homedir(), "AppData", "Local"),
    "linear-cli-tool",
    "node_modules",
    ".bin",
    process.platform === "win32" ? "linear.cmd" : "linear",
  );
  if (fs.existsSync(localTool)) {
    return shQuote(localTool);
  }
  return "npx --yes --prefix %LOCALAPPDATA%\\linear-cli-tool @schpet/linear-cli";
}

function shQuote(value) {
  return `"${String(value).replace(/"/g, '\\"')}"`;
}

const LINEAR = resolveLinearCmd();
const WORKSPACE = process.env.LINEAR_WORKSPACE || "staqbot";
const TEAM = process.env.LINEAR_TEAM || "STA";
const PROJECT = process.env.LINEAR_MARKETPLACE_PROJECT || "Gravitre Marketplace";

/** Linear priority: 1=Urgent, 2=High, 3=Normal, 4=Low */
const P = { P0: 1, P1: 2, P2: 3 };

const MILESTONES = [
  {
    key: "m1",
    ref: "M1",
    title: "[M1] Stage 1 hardening (current sprint)",
    description:
      "Close Stage 1 gaps from June 2026 marketplace architecture audit: catalog depth, browse fixes, frontend polish, structured metadata, tests, docs. Keep unified `marketplace_assets` as canonical — do not merge v0 branches blindly.",
    priority: P.P1,
  },
  {
    key: "m2",
    ref: "M2",
    title: "[M2] Stage 2 internal marketplace",
    description:
      "Org-scoped asset CRUD, internal publish workflow, approval queue, uninstall, adoption analytics. Schema-ready; APIs/UI missing per audit.",
    priority: P.P1,
  },
  {
    key: "m3",
    ref: "M3",
    title: "[M3] Stage 3 community (unified assets)",
    description:
      "Public publishing, creator onboarding, Gravitre review queue for unified assets (not partner connector track). Architecture-ready placeholders.",
    priority: P.P2,
  },
  {
    key: "m4",
    ref: "M4",
    title: "[M4] Ecosystem expansion",
    description:
      "Paid assets, revenue share, connector marketplace convergence, ROI/strategic-hours dashboard.",
    priority: P.P2,
  },
  {
    key: "m5",
    ref: "M5",
    title: "[M5] Production hardening & publisher growth",
    description:
      "Harden M4 monetization in production, publisher revenue analytics, and paid asset authoring UI.",
    priority: P.P1,
  },
];

const ISSUES = [
  // ── M1 ──
  {
    milestone: "m1",
    ref: "MKT-AUDIT-ARCH-1",
    title: "Document dual-marketplace convergence decision",
    priority: P.P2,
    estimate: 2,
    deps: [],
    description: `## Description
Decide and document whether the partner connector track converges into \`asset_type: connector_config\` within unified \`marketplace_assets\`, or remains a permanent separate federation layer.

## Technical requirements
- Read \`docs/integration/agent-role-marketplace.md\` and partner marketplace migrations
- Document decision in integration docs

## Acceptance criteria
- [ ] Decision documented in \`docs/integration/agent-role-marketplace.md\`
- [ ] If converging: follow-up issue created in M3/M4 for migration
- [ ] If separate: partner track marked out of scope for unified-asset features

## Implementation notes
Audit Section 2 — open architectural decision before Stage 3 community work.`,
  },
  {
    milestone: "m1",
    ref: "MKT-AUDIT-4.6",
    title: "Add business_outcome, use_case, estimated_hours_saved columns",
    priority: P.P1,
    estimate: 5,
    deps: [],
    description: `## Description
Promote outcome metadata from implicit JSON copy to first-class \`marketplace_assets\` columns.

## Technical requirements
- Migration: \`business_outcome TEXT\`, \`use_case TEXT\`, \`estimated_hours_saved NUMERIC(6,1)\`
- \`backend/scripts/backfill_asset_outcome_columns.py\` (re-runnable)
- Expose fields in browse/detail serializers (\`backend/app/marketplace/browse.py\`)

## Dependencies
None — blocks catalog expansion (MKT-AUDIT-4.5)

## Acceptance criteria
- [ ] Migration applied
- [ ] 27 seed assets backfilled
- [ ] API returns new fields on asset list/detail

## Implementation notes
Dependency for expanding catalog with structured outcome fields.`,
  },
  {
    milestone: "m1",
    ref: "MKT-AUDIT-4.5",
    title: "Expand starter catalog 27 → 50 assets",
    priority: P.P0,
    estimate: 13,
    deps: ["MKT-AUDIT-4.6"],
    description: `## Description
Add 23 high-quality Gravitre-owned assets (depth, not filler) to reach 50-asset Stage 1 minimum.

## Technical requirements
- Extend \`backend/app/marketplace/seed_catalog.py\` (or category modules)
- Match quality bar of existing 27 (real prompts, workflow graphs, RAG seeds)
- \`backend/tests/test_marketplace_seed_idempotency.py\`: re-run seed does not duplicate

## Dependencies
MKT-AUDIT-4.6 (structured outcome columns)

## Acceptance criteria
- [ ] \`list_catalog_assets()\` returns ≥50 assets
- [ ] All assets pass \`validate_asset_payload(..., publish=True)\`
- [ ] Seed script idempotent

## Implementation notes
Original spec categories already represented — this is depth expansion within departments.`,
  },
  {
    milestone: "m1",
    ref: "MKT-AUDIT-5.4",
    title: "Fix internal visibility in browse query",
    priority: P.P1,
    estimate: 3,
    deps: [],
    description: `## Description
Browse must return internal published assets for owning org only; never leak other orgs' internal assets.

## Technical requirements
- Fix \`backend/app/marketplace/browse.py\` list filter (currently \`public OR org_id\` — misses internal visibility rules)
- \`backend/tests/test_marketplace_browse_visibility.py\`

## Acceptance criteria
- [ ] Public published assets visible to all orgs
- [ ] Internal published assets visible to owning org only
- [ ] Internal assets hidden from other orgs
- [ ] Private drafts never in browse results

## Implementation notes
Security-relevant — test cross-org non-leak explicitly.`,
  },
  {
    milestone: "m1",
    ref: "MKT-AUDIT-5.5",
    title: "Tests for department_pack and knowledge_pack install paths",
    priority: P.P1,
    estimate: 5,
    deps: [],
    description: `## Description
Install paths exist but lack test coverage per audit.

## Technical requirements
- \`backend/tests/test_marketplace_install_department_pack.py\`
- \`backend/tests/test_marketplace_install_knowledge_pack.py\`
- Fix install bugs if tests reveal breakage

## Acceptance criteria
- [ ] Department pack: creates pack items, increments counters, partial failure summary
- [ ] Knowledge pack: creates RAG source, respects plan limits
- [ ] All new tests pass in CI

## Implementation notes
Audit flagged "looks done, isn't verified" gap.`,
  },
  {
    milestone: "m1",
    ref: "MKT-AUDIT-5.6",
    title: "Surface LIMIT_EXCEEDED structured error on install",
    priority: P.P1,
    estimate: 3,
    deps: [],
    description: `## Description
Agent/workflow plan limits block installs with opaque errors — return machine-readable payload for UI.

## Technical requirements
- \`backend/app/marketplace/service.py\` \`_check_plan_limits\`
- Response shape: \`error: plan_limit_exceeded\`, \`limit_type\`, \`current\`, \`max\`, \`upgrade_url\`
- \`backend/tests/test_marketplace_plan_limits.py\`

## Acceptance criteria
- [ ] Limit exceeded returns structured JSON (not bare 403)
- [ ] Includes upgrade path \`/settings/billing\`
- [ ] Tests cover agent and workflow limits

## Implementation notes
Known prod issue from audit risk table.`,
  },
  {
    milestone: "m1",
    ref: "MKT-AUDIT-6.2",
    title: "Clickable category and department facet filters",
    priority: P.P1,
    estimate: 5,
    deps: [],
    description: `## Description
Wire \`GET /categories\` facet counts to filter UI on browse page.

## Technical requirements
- \`apps/web/app/marketplace/assets/page.tsx\`
- \`marketplaceApi.listAssets({ department, category, pricingType })\`

## Acceptance criteria
- [ ] Sidebar/top facets clickable and update asset grid
- [ ] URL reflects active filters
- [ ] Empty state when filter matches zero assets

## Implementation notes
API client already supports filters; UI missing per v0 handoff spec.`,
  },
  {
    milestone: "m1",
    ref: "MKT-AUDIT-6.3",
    title: "Dedicated /marketplace/assets/[slug] route",
    priority: P.P2,
    estimate: 5,
    deps: [],
    description: `## Description
Shareable asset detail route; sync URL when drawer opens/closes.

## Technical requirements
- \`apps/web/app/marketplace/assets/[slug]/page.tsx\` or parallel route
- Reuse detail drawer component from browse page

## Acceptance criteria
- [ ] Direct navigation to slug loads asset detail
- [ ] Browser back/forward works
- [ ] Deep links from install success still work

## Implementation notes
Drawer-only detail today; \`?slug=\` only on initial load.`,
  },
  {
    milestone: "m1",
    ref: "MKT-AUDIT-6.4",
    title: "Marketplace analytics dashboard UI",
    priority: P.P1,
    estimate: 5,
    deps: [],
    description: `## Description
Wire \`GET /api/marketplace/analytics/summary\` proxy to a marketplace analytics page.

## Technical requirements
- Add \`marketplaceApi.analyticsSummary\` in \`apps/web/lib/api.ts\`
- New page under \`apps/web/app/marketplace/analytics/page.tsx\`

## Acceptance criteria
- [ ] Admin/org admin can view catalog + org install aggregates
- [ ] Uses live API (no mocks)
- [ ] Linked from marketplace home

## Implementation notes
Proxy exists; no client method or page today.`,
  },
  {
    milestone: "m1",
    ref: "MKT-AUDIT-6.5",
    title: "Reviews and saves UI",
    priority: P.P2,
    estimate: 8,
    deps: [],
    description: `## Description
Expose review list/submit and save/wishlist using existing backend routes.

## Technical requirements
- \`apps/web/lib/api.ts\` methods for reviews/saves
- UI on asset detail drawer

## Acceptance criteria
- [ ] User can save/unsave asset
- [ ] Org member can submit review; average rating updates
- [ ] Proxies already under \`apps/web/app/api/marketplace/**\`

## Implementation notes
Backend + proxies exist; frontend missing.`,
  },
  {
    milestone: "m1",
    ref: "MKT-AUDIT-6.6",
    title: "Remove legacy role-pack client and fix CS dashboard links",
    priority: P.P1,
    estimate: 3,
    deps: [],
    description: `## Description
Remove dead \`listRolePacks\` / \`installRolePack\` client methods; fix broken \`/marketplace/role-packs?pack=\` links.

## Technical requirements
- \`apps/web/lib/api.ts\`, \`apps/web/types/api.ts\`
- \`apps/web/components/enterprise/cs-dashboard-tab.tsx\`
- grep zero \`/marketplace/role-packs\` references (except redirect route if kept)

## Acceptance criteria
- [ ] CS dashboard links to unified marketplace equivalent
- [ ] No unused role-pack API methods in client
- [ ] Redirect route still works for bookmarks

## Implementation notes
Bundle CS deep-link fix with this cleanup (audit explicit issue).`,
  },
  {
    milestone: "m1",
    ref: "MKT-AUDIT-DOC-1",
    title: "Update V0_BACKEND_SYNC.md branch reference",
    priority: P.P2,
    estimate: 1,
    deps: [],
    description: `## Description
Sync doc references old v0 branch \`8b623736\`; current is \`c5e410cc\`. De-emphasize legacy role-packs.

## Technical requirements
- \`docs/integration/V0_BACKEND_SYNC.md\`

## Acceptance criteria
- [ ] Branch id corrected to \`v0/cesarbohorquezjr-4251-c5e410cc\`
- [ ] Unified \`/api/marketplace/assets\` documented as canonical

## Implementation notes
Audit Section 12 documentation debt.`,
  },
  {
    milestone: "m1",
    ref: "MKT-AUDIT-QA-1",
    title: "E2E marketplace smoke in CI",
    priority: P.P2,
    estimate: 5,
    deps: [],
    description: `## Description
Add CI job running \`scripts/smoke-marketplace-production.py\` or backend install smoke against staging.

## Technical requirements
- GitHub Actions workflow or extend existing smoke pipeline
- Document required secrets

## Acceptance criteria
- [ ] CI fails if marketplace browse/install smoke fails
- [ ] Documented in \`docs/integration/agent-role-marketplace.md\`

## Implementation notes
Regression guard after v0 merge incidents (PR #52).`,
  },
  // ── M2 ──
  {
    milestone: "m2",
    ref: "MKT-AUDIT-9.1",
    title: "Asset CRUD API (POST/PATCH/DELETE draft assets)",
    priority: P.P0,
    estimate: 8,
    deps: [],
    description: `## Description
No asset create/update path blocks all of Stage 2. Add org-admin CRUD for org-owned drafts.

## Technical requirements
- \`POST /api/marketplace/assets\`, \`PATCH /api/marketplace/assets/{id}\`, \`DELETE\` (soft archive)
- Reuse \`backend/app/marketplace/schemas.py\` validation + secret scan
- Audit: \`marketplace.asset.created|updated|archived\`
- \`backend/tests/test_marketplace_asset_crud.py\`

## Acceptance criteria
- [ ] Create draft as org admin; reject non-admin
- [ ] PATCH only draft/pending_review; reject published direct PATCH
- [ ] Archive soft-deletes; installs still resolve via version snapshots

## Implementation notes
**Stage 2 unblocker** — audit highest-leverage gap.`,
  },
  {
    milestone: "m2",
    ref: "MKT-AUDIT-9.2",
    title: "Internal publish workflow (draft → review → published)",
    priority: P.P0,
    estimate: 8,
    deps: ["MKT-AUDIT-9.1"],
    description: `## Description
State machine for org-internal publishing: submit, approve, reject.

## Technical requirements
- \`POST .../submit-for-review\`, \`/approve\`, \`/reject\`
- Stricter validation at submit vs draft save
- Approve defaults \`visibility=internal\` (not public — Stage 3 separate)
- \`backend/tests/test_marketplace_publish_workflow.py\`

## Dependencies
MKT-AUDIT-9.1

## Acceptance criteria
- [ ] submit transitions draft → pending_review with strict validation
- [ ] approve requires admin; sets internal visibility
- [ ] reject returns to draft with reason

## Implementation notes
Distinct from Stage 3 Gravitre public review queue.`,
  },
  {
    milestone: "m2",
    ref: "MKT-AUDIT-9.3",
    title: "Admin approval queue UI for org-published assets",
    priority: P.P0,
    estimate: 5,
    deps: ["MKT-AUDIT-9.2"],
    description: `## Description
Internal marketplace admin queue (unified assets) — not partner connector admin page.

## Technical requirements
- New page e.g. \`apps/web/app/marketplace/org-admin/page.tsx\`
- Lists \`pending_review\` org assets; approve/reject actions

## Dependencies
MKT-AUDIT-9.2

## Acceptance criteria
- [ ] Org admin sees pending internal assets
- [ ] Approve/reject updates status via API
- [ ] Linked from marketplace nav for admins

## Implementation notes
Existing \`/marketplace/admin\` is partner submissions only.`,
  },
  {
    milestone: "m2",
    ref: "MKT-AUDIT-9.4",
    title: "Version snapshot on org asset publish",
    priority: P.P1,
    estimate: 5,
    deps: ["MKT-AUDIT-9.2"],
    description: `## Description
Extend existing \`marketplace_asset_versions\` — snapshots today are seed-only.

## Technical requirements
- \`backend/app/marketplace/versions.py\` write path on approve/publish
- Tests alongside rollback tests

## Dependencies
MKT-AUDIT-9.2

## Acceptance criteria
- [ ] Each publish creates new version row
- [ ] Rollback still works for org-owned assets

## Implementation notes
Rollback API exists; publish snapshots missing.`,
  },
  {
    milestone: "m2",
    ref: "MKT-AUDIT-8.1",
    title: "Uninstall / disable installed asset flow",
    priority: P.P1,
    estimate: 5,
    deps: [],
    description: `## Description
Allow org admin to mark install inactive / uninstall with audit trail.

## Technical requirements
- API endpoint updating \`marketplace_installs.status\`
- Optional: disable created entities (agents/workflows) per policy

## Acceptance criteria
- [ ] Admin can uninstall asset from org
- [ ] Installed page reflects inactive status
- [ ] Audit event recorded

## Implementation notes
Schema supports \`uninstalled\` status; UI/API missing.`,
  },
  {
    milestone: "m2",
    ref: "MKT-AUDIT-10.2",
    title: "Per-asset adoption events table",
    priority: P.P1,
    estimate: 8,
    deps: [],
    description: `## Description
Track views, active usage, workflow/agent runs tied to marketplace installs for ROI dashboard.

## Technical requirements
- New table e.g. \`marketplace_usage_events\` (unified assets — separate from partner connector usage)
- Ingest hooks from agent/workflow run completion

## Acceptance criteria
- [ ] Migration + RLS
- [ ] Event recorded on agent run for installed asset
- [ ] Analytics summary exposes top assets by usage

## Implementation notes
Distinct from install/clone counters (MKT-10.1 done as STA-217).`,
  },
  {
    milestone: "m2",
    ref: "MKT-AUDIT-6.7",
    title: "Org marketplace tab (shared in your organization)",
    priority: P.P1,
    estimate: 5,
    deps: ["MKT-AUDIT-5.4", "MKT-AUDIT-9.2"],
    description: `## Description
Browse org-internal published assets separately from Gravitre public catalog.

## Technical requirements
- UI tab filtering \`visibility=internal\` + org publisher
- Depends on browse fix and publish workflow

## Dependencies
MKT-AUDIT-5.4, MKT-AUDIT-9.2

## Acceptance criteria
- [ ] Tab shows only org-shared internal assets
- [ ] Install/clone flows work for internal assets

## Implementation notes
Stage 2 UX centerpiece.`,
  },
  // ── M3 placeholders ──
  {
    milestone: "m3",
    ref: "MKT-AUDIT-11.1",
    title: "Creator publisher onboarding (org → publisher profile)",
    priority: P.P2,
    estimate: 5,
    deps: ["MKT-AUDIT-9.2"],
    description: `Placeholder — Stage 3: allow approved orgs to become marketplace publishers for public assets.`,
  },
  {
    milestone: "m3",
    ref: "MKT-AUDIT-11.2",
    title: "Gravitre review queue for unified public assets",
    priority: P.P2,
    estimate: 8,
    deps: ["MKT-AUDIT-11.1"],
    description: `Placeholder — Stage 3: platform reviewer workflow for \`pending_review\` public submissions (unified assets, not partner connectors).`,
  },
  {
    milestone: "m3",
    ref: "MKT-AUDIT-11.3",
    title: "Featured and verified asset flags",
    priority: P.P2,
    estimate: 3,
    deps: [],
    description: `Placeholder — Stage 3: featured assets on marketplace home; verified badge beyond publisher.verified.`,
  },
  // ── M4 placeholders ──
  {
    milestone: "m4",
    ref: "MKT-AUDIT-12.1",
    title: "Paid install entitlement check + Stripe checkout stub",
    priority: P.P2,
    estimate: 8,
    deps: [],
    description: `Placeholder — Phase 4: gate install on org entitlement; Stripe checkout for one-time/subscription packs.`,
  },
  {
    milestone: "m4",
    ref: "MKT-AUDIT-12.2",
    title: "Creator revenue share → Stripe transfers",
    priority: P.P2,
    estimate: 8,
    deps: ["MKT-AUDIT-12.1"],
    description: `Placeholder — Phase 4: wire \`marketplace_payouts\` ledger to Stripe Connect transfers (70/30 or 80/20).`,
  },
  {
    milestone: "m4",
    ref: "MKT-AUDIT-13.1",
    title: "Converge partner registry with connector_config assets",
    priority: P.P2,
    estimate: 13,
    deps: ["MKT-AUDIT-ARCH-1"],
    description: `Placeholder — Depends on dual-marketplace decision. Unify or federate partner connectors into unified catalog.`,
  },
  {
    milestone: "m4",
    ref: "MKT-AUDIT-13.2",
    title: "Strategic hours saved ROI dashboard",
    priority: P.P2,
    estimate: 8,
    deps: ["MKT-AUDIT-10.2"],
    description: `Placeholder — Correlate install → usage → estimated_hours_saved for executive ROI reporting.`,
  },
  // ── M5 ──
  {
    milestone: "m5",
    ref: "MKT-AUDIT-14.1",
    title: "Publisher revenue analytics dashboard",
    priority: P.P1,
    estimate: 8,
    deps: ["MKT-AUDIT-12.2"],
    description: `## Description
Executive and publisher-facing dashboard for marketplace revenue: gross sales, platform fees, pending/transferred payouts, and usage correlation.

## Technical requirements
- Aggregate \`marketplace_payouts\`, \`marketplace_usage_events\`, and asset adoption metrics
- Publisher org admin view on \`/marketplace/billing\` or dedicated analytics route
- API: \`GET /api/marketplace/publisher/analytics\`

## Acceptance criteria
- [ ] Publisher sees earnings summary + recent payout rows
- [ ] Platform admin can spot-check top earning assets (optional v1 scope)
- [ ] Tests for aggregation service`,
  },
  {
    milestone: "m5",
    ref: "MKT-AUDIT-14.2",
    title: "Paid asset pricing in org/platform admin UI",
    priority: P.P1,
    estimate: 5,
    deps: ["MKT-AUDIT-12.1"],
    description: `## Description
Allow org admins and platform admins to set \`pricing_type\` and \`price_cents\` on unified marketplace assets.

## Technical requirements
- Extend asset PATCH/create forms in org-admin and platform-admin
- Validate pricing_type in (free, paid, subscription) and price_cents >= 0
- Surface price badge on browse/detail (already partial)

## Acceptance criteria
- [ ] Org admin can mark internal asset as paid with price
- [ ] Platform admin can set pricing on public catalog assets
- [ ] Backend validation + tests`,
  },
  {
    milestone: "m5",
    ref: "MKT-AUDIT-14.3",
    title: "Publisher payout sync UI on marketplace billing",
    priority: P.P2,
    estimate: 3,
    deps: ["MKT-AUDIT-12.2"],
    description: `## Description
Wire existing \`POST /api/marketplace/publisher/payouts/sync\` to the partner billing page with status feedback.

## Acceptance criteria
- [ ] Billing page shows payout summary from \`marketplace_payouts\`
- [ ] Sync button retries pending Connect transfers
- [ ] Toast + refreshed summary after sync`,
  },
];

function run(cmd, opts = {}) {
  const result = spawnSync(cmd, {
    shell: true,
    encoding: "utf-8",
    stdio: opts.capture ? ["inherit", "pipe", "pipe"] : "inherit",
    env: { ...process.env, FORCE_COLOR: "0" },
  });
  if (result.status !== 0) {
    const err = (result.stderr || result.stdout || "").trim();
    throw new Error(err || `Command failed: ${cmd}`);
  }
  return (result.stdout || "").trim();
}

function parseIssueId(output) {
  const match = output.match(/\b([A-Z]{2,10}-\d+)\b/);
  return match?.[1] ?? null;
}

function fetchExistingRefs() {
  try {
    const raw = run(
      `${LINEAR} issue query --project ${shQuote(PROJECT)} --all-teams --limit 0 -j`,
      { capture: true },
    );
    const data = JSON.parse(raw);
    const refs = new Set();
    for (const node of data.nodes ?? []) {
      const m = node.title?.match(/\[([A-Z0-9.-]+)\]/);
      if (m) refs.add(m[1]);
      if (node.title?.includes("MKT-AUDIT-")) {
        const audit = node.title.match(/\[MKT-AUDIT-[A-Z0-9.-]+\]/);
        if (audit) refs.add(audit[0].slice(1, -1));
      }
    }
    return refs;
  } catch (e) {
    console.warn("⚠ Could not fetch existing issues:", e.message.split("\n")[0]);
    return new Set();
  }
}

function createIssue({ title, description, parent, priority, estimate, labels }) {
  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "linear-mkt-"));
  const descFile = path.join(tmpDir, "desc.md");
  fs.writeFileSync(descFile, description, "utf-8");

  const parts = [
    LINEAR,
    "issue create",
    "--no-interactive",
    `-t ${shQuote(title)}`,
    `--description-file ${shQuote(descFile)}`,
    `--team ${shQuote(TEAM)}`,
    `--project ${shQuote(PROJECT)}`,
  ];
  if (parent) parts.push(`--parent ${shQuote(parent)}`);
  if (priority) parts.push(`-p ${priority}`);
  if (estimate) parts.push(`--estimate ${estimate}`);
  for (const label of labels ?? []) {
    parts.push(`-l ${shQuote(label)}`);
  }

  const output = run(parts.join(" "), { capture: true });
  fs.rmSync(tmpDir, { recursive: true, force: true });
  const id = parseIssueId(output);
  if (!id) throw new Error(`Could not parse issue id from:\n${output}`);
  return id;
}

function ensureLabels() {
  const names = ["marketplace", "marketplace-audit", "stage-1", "stage-2", "unified-assets"];
  for (const name of names) {
    try {
      run(`${LINEAR} label create -n ${shQuote(name)} -t ${shQuote(TEAM)} -c "#9B59B6"`, {
        capture: true,
      });
    } catch {
      /* exists */
    }
  }
}

function main() {
  console.log(`\n📋 Gravitre Marketplace audit backlog → Linear (${PROJECT})\n`);

  const existing = fetchExistingRefs();
  console.log(`   Found ${existing.size} tagged issues already in project (by bracket ref).\n`);

  ensureLabels();

  const milestoneIds = {};
  console.log("📦 Milestones (parent epics)...");
  for (const ms of MILESTONES) {
    if (existing.has(ms.ref)) {
      console.log(`   · skip ${ms.ref} (already exists)`);
      continue;
    }
    const id = createIssue({
      title: ms.title,
      description: ms.description,
      priority: ms.priority,
      estimate: 3,
      labels: ["marketplace", "marketplace-audit"],
    });
    milestoneIds[ms.key] = id;
    existing.add(ms.ref);
    console.log(`   ✓ ${id}  ${ms.title}`);
  }

  // Re-fetch milestone IDs if skipped (search by title)
  for (const ms of MILESTONES) {
    if (milestoneIds[ms.key]) continue;
    try {
      const raw = run(
        `${LINEAR} issue query --search ${shQuote(ms.ref)} --project ${shQuote(PROJECT)} --all-teams --limit 5 -j`,
        { capture: true },
      );
      const nodes = JSON.parse(raw).nodes ?? [];
      const hit = nodes.find((n) => n.title === ms.title);
      if (hit) milestoneIds[ms.key] = hit.identifier;
    } catch {
      /* ignore */
    }
  }

  const created = [];
  const skipped = [];
  const refToLinear = {};
  const idsPath = path.join(__dirname, "..", "docs", "integration", "marketplace-audit-linear-ids.json");
  if (fs.existsSync(idsPath)) {
    try {
      const doc = JSON.parse(fs.readFileSync(idsPath, "utf-8"));
      for (const item of doc.created || []) {
        if (item.ref && item.linear) refToLinear[item.ref] = item.linear;
      }
    } catch {
      /* ignore */
    }
  }

  console.log("\n📝 Audit issues...");
  for (const issue of ISSUES) {
    if (existing.has(issue.ref)) {
      skipped.push(issue.ref);
      console.log(`   · skip [${issue.ref}] (exists)`);
      continue;
    }
    const parent = milestoneIds[issue.milestone];
    const title = `[${issue.ref}] ${issue.title}`;
    const id = createIssue({
      title,
      description: issue.description,
      parent,
      priority: issue.priority,
      estimate: issue.estimate,
      labels: ["marketplace", "marketplace-audit", "unified-assets"],
    });
    refToLinear[issue.ref] = id;
    created.push({ ref: issue.ref, linear: id, title: issue.title, milestone: issue.milestone });
    existing.add(issue.ref);
    console.log(`   ✓ ${id}  [${issue.ref}] ${issue.title}`);
  }

  // Link dependencies
  console.log("\n🔗 Dependencies...");
  for (const issue of ISSUES) {
    if (!issue.deps?.length) continue;
    const blocked = refToLinear[issue.ref];
    if (!blocked) continue;
    for (const depRef of issue.deps) {
      const blocker = refToLinear[depRef];
      if (!blocker) continue;
      try {
        run(
          `${LINEAR} issue relation add ${shQuote(blocked)} blocked-by ${shQuote(blocker)}`,
          { capture: true },
        );
        console.log(`   ✓ ${blocked} blocked by ${blocker}`);
      } catch (e) {
        console.warn(`   ⚠ relation ${blocked}←${blocker}: ${e.message.split("\n")[0]}`);
      }
    }
  }

  const outPath = path.join(__dirname, "..", "docs", "integration", "marketplace-audit-linear-ids.json");
  fs.mkdirSync(path.dirname(outPath), { recursive: true });
  let existingDoc = { milestones: {}, created: [], skipped: [] };
  if (fs.existsSync(outPath)) {
    try {
      existingDoc = JSON.parse(fs.readFileSync(outPath, "utf-8"));
    } catch {
      /* fresh write */
    }
  }
  const mergedMilestones = { ...(existingDoc.milestones || {}), ...milestoneIds };
  const mergedCreated = [...(existingDoc.created || []), ...created];
  const mergedSkipped = [...new Set([...(existingDoc.skipped || []), ...skipped])];
  fs.writeFileSync(
    outPath,
    JSON.stringify(
      {
        createdAt: new Date().toISOString(),
        project: PROJECT,
        milestones: mergedMilestones,
        created: mergedCreated,
        skipped: mergedSkipped,
        projectUrl: `https://linear.app/${WORKSPACE}/project/gravitre-marketplace`,
      },
      null,
      2,
    ),
  );

  const m1 = mergedCreated.filter((c) => c.milestone === "m1").length;
  const m2 = mergedCreated.filter((c) => c.milestone === "m2").length;
  const m3 = mergedCreated.filter((c) => c.milestone === "m3").length;
  const m4 = mergedCreated.filter((c) => c.milestone === "m4").length;
  const m5 = mergedCreated.filter((c) => c.milestone === "m5").length;

  console.log("\n✅ LINEAR BACKLOG CREATED");
  console.log(`   M1 — Stage 1 hardening: ${m1} issues created (${skipped.filter(() => false)})`);
  console.log(`   M2 — Stage 2: ${m2} issues created`);
  console.log(`   M3/M4 — placeholders: ${m3 + m4} issues in registry`);
  console.log(`   M5 — publisher growth: ${m5} issues created this run`);
  console.log(`   Skipped (already existed): ${skipped.length} refs`);
  if (skipped.length) console.log(`     ${skipped.join(", ")}`);
  console.log(`\n   Linear project: https://linear.app/${WORKSPACE}/project/gravitre-marketplace`);
  console.log(`   IDs saved: docs/integration/marketplace-audit-linear-ids.json\n`);
}

main();
