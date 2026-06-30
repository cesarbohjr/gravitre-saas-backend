#!/usr/bin/env node
/**
 * Create Marketing Operations Pack Phase 5–8 audit tickets in Linear.
 *
 * Usage:
 *   npm run linear:marketing-pack-audit
 *   # or with key already in env:
 *   node scripts/create-marketing-pack-audit-linear-issues.mjs
 *
 * Auth (first match wins):
 *   LINEAR_API_KEY / LINEAR_TOKEN env
 *   Railway service vars (via scripts/run-marketing-pack-audit-linear.ps1)
 *   @schpet/linear-cli keyring (`linear auth login`)
 */
import { spawnSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const WORKSPACE = process.env.LINEAR_WORKSPACE || "staqbot";
const TEAM_KEY = process.env.LINEAR_TEAM || "Staqbot";
const RAILWAY_SERVICE = process.env.RAILWAY_SERVICE || "gravitre-saas-backend";

function resolveLinearCmd() {
  if (process.env.LINEAR_CLI_BIN) return process.env.LINEAR_CLI_BIN;
  const localTool = path.join(
    process.env.LOCALAPPDATA || path.join(os.homedir(), "AppData", "Local"),
    "linear-cli-tool",
    "node_modules",
    ".bin",
    process.platform === "win32" ? "linear.cmd" : "linear",
  );
  if (fs.existsSync(localTool)) return localTool;
  return null;
}

function getApiKeyFromRailway() {
  const result = spawnSync(
    "railway",
    ["variables", "--service", RAILWAY_SERVICE, "--json"],
    { encoding: "utf8", shell: true },
  );
  if (result.status !== 0) return null;
  try {
    const vars = JSON.parse(result.stdout || "{}");
    const key = String(vars.LINEAR_API_KEY || vars.LINEAR_TOKEN || "").trim();
    return key || null;
  } catch {
    return null;
  }
}

function getApiKey() {
  const fromEnv = process.env.LINEAR_API_KEY || process.env.LINEAR_TOKEN;
  if (fromEnv?.trim()) return fromEnv.trim();

  const fromRailway = getApiKeyFromRailway();
  if (fromRailway) return fromRailway;

  const linearCmd = resolveLinearCmd();
  if (!linearCmd) return null;
  const result = spawnSync(linearCmd, ["auth", "token", "--workspace", WORKSPACE], {
    encoding: "utf8",
    shell: true,
  });
  if (result.status !== 0) return null;
  return (result.stdout || "").trim() || null;
}

async function gql(apiKey, query, variables = {}) {
  const res = await fetch("https://api.linear.app/graphql", {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: apiKey },
    body: JSON.stringify({ query, variables }),
  });
  const json = await res.json();
  if (json.errors?.length) {
    throw new Error(json.errors.map((e) => e.message).join("; "));
  }
  return json.data;
}

async function getTeam(apiKey) {
  const data = await gql(
    apiKey,
    `query($key: String!) {
      teams(filter: { key: { eq: $key } }) {
        nodes { id key name labels { nodes { id name } } }
      }
    }`,
    { key: TEAM_KEY },
  );
  const team = data.teams?.nodes?.[0];
  if (!team) throw new Error(`Linear team not found: ${TEAM_KEY}`);
  return team;
}

async function ensureLabel(apiKey, teamId, labelName, existingLabels) {
  const found = existingLabels.find((l) => l.name === labelName);
  if (found) return found.id;
  const data = await gql(
    apiKey,
    `mutation($input: IssueLabelCreateInput!) {
      issueLabelCreate(input: $input) { success issueLabel { id name } }
    }`,
    { input: { teamId, name: labelName, color: "#9B59B6" } },
  );
  return data.issueLabelCreate.issueLabel.id;
}

async function findIssueByTitle(apiKey, teamId, title) {
  const data = await gql(
    apiKey,
    `query($teamId: ID!, $title: String!) {
      team(id: $teamId) {
        issues(filter: { title: { eq: $title } }, first: 1) {
          nodes { id identifier title }
        }
      }
    }`,
    { teamId, title },
  );
  return data.team?.issues?.nodes?.[0] || null;
}

async function createIssue(apiKey, teamId, labelIds, issue) {
  const existing = await findIssueByTitle(apiKey, teamId, issue.title);
  if (existing) {
    console.log(`${issue.key}: ${existing.identifier} (exists)`);
    return existing.identifier;
  }

  const data = await gql(
    apiKey,
    `mutation($input: IssueCreateInput!) {
      issueCreate(input: $input) {
        success
        issue { identifier title url }
      }
    }`,
    {
      input: {
        teamId,
        title: issue.title,
        description: issue.description,
        labelIds,
      },
    },
  );
  const created = data.issueCreate?.issue;
  if (!created) throw new Error(`Failed to create: ${issue.title}`);
  console.log(`${issue.key}: ${created.identifier}`);
  return created.identifier;
}

const ISSUES = [
  {
    key: "5.1",
    title: "[MKT-PACK-AUDIT 5.1] Agent chaining + department_pack mapping",
    labels: ["marketing-pack-audit", "phase-5"],
    description: `**Status:** Partial / expressible

- 4-agent chain expressible via graph + \`handoff_service.execute_agent_step_with_handoff()\` (\`next_agent_id\`).
- \`department_pack\` marketplace type exists; seed \`marketing-operations-pack\` ships 2 agents (content gap vs 4-agent target).
- Independent agent versioning: per-agent only; no pack-coordinated semver.

**Files:** \`backend/app/services/handoff_service.py\`, \`backend/app/workflows/execution_engine_runtime.py\`, \`backend/app/marketplace/seed_catalog.py\``,
  },
  {
    key: "5.2",
    title: "[MKT-PACK-AUDIT 5.2] Batch + partial approval — MISSING",
    labels: ["marketing-pack-audit", "phase-5", "platform-gap"],
    description: `**Status:** Missing (unchanged by consolidation)

- No batch grouping for approval over multiple items.
- No partial approve/reject within a batch.
- \`on_reject\` only \`fail_workflow\` or \`skip\` — no route to specific upstream agent.

**Needed:** data model (batch grouping), UI (partial-select), orchestration (selective re-entry).

**Files:** \`backend/app/workflows/execution_engine_runtime.py\` lines 98–103, 731–756`,
  },
  {
    key: "6.1",
    title: "[MKT-PACK-AUDIT 6.1] Connector gaps checklist",
    labels: ["marketing-pack-audit", "phase-6", "connectors"],
    description: `Reconfirmed connector state:

- [x] Apollo.io — partial (API key, tools exist)
- [x] Notion — partial (OAuth + sync)
- [x] Google Drive — partial (Google OAuth + tools)
- [ ] Dropbox — **missing**
- [x] Canva — partial (OAuth + tools)
- [ ] Adobe Creative Cloud — **missing** (Marketo only)
- [ ] Engagebay — **missing**
- [ ] LinkedIn publishing — **partial** (enrich/ads only; no organic publish / w_member_social)

**LinkedIn flag:** publish requires new write-scope actions + partner approval.`,
  },
  {
    key: "6.2",
    title: "[MKT-PACK-AUDIT 6.2] Outcome feedback loop — Mode A extend / Mode B net-new",
    labels: ["marketing-pack-audit", "phase-6"],
    description: `**Mode A (human-approved suggestions):** Extend \`CompanyIntelligenceOrchestrator\`, \`outcome_attribution_service.py\`, integration suggestions — not wired to post-publish marketing metrics yet.

**Mode B (autonomous replanning):** Does NOT exist platform-wide. Net-new: auto tone/cadence shifts, caps, rollback, audit without approval anchor.

See dedicated Mode A/B decision ticket for product sign-off.`,
  },
  {
    key: "6.2-decision",
    title: "[MKT-PACK DECISION] Mode A/B feedback — awaiting pack-owner sign-off",
    labels: ["marketing-pack-audit", "product-decision"],
    description: `**Recommended default:** Mode A (human-approved suggestions).

**Mode B:** Opt-in only; net-new platform work; brand-voice-affecting.

**If Mode B approved, guardrails required:**
- Cap on behavior shift per cycle
- Rollback if new behavior underperforms
- Post-hoc audit trail (what changed, why, no prior human approval)

**Pricing (pending):** Mode B included with risk gate vs +$49/mo add-on — product decision.

**Status:** Awaiting pack-owner sign-off on default and whether Mode B ships at all.

**Assign to:** Product owner for Marketing Operations Pack — NOT engineering.`,
  },
  {
    key: "7.1",
    title: "[MKT-PACK-AUDIT 7.1] Brand/positioning knowledge store",
    labels: ["marketing-pack-audit", "phase-7"],
    description: `**Recommendation:** RAG-source-based on \`UnifiedRetrievalService\` + department-scoped RAG (\`20260602130000_department_scoped_rag.sql\`).

Structured brand store not required for v1; pack seed includes \`rag:brand-voice\` doc placeholder.`,
  },
  {
    key: "7.2",
    title: "[MKT-PACK-AUDIT 7.2] Audit/versioning",
    labels: ["marketing-pack-audit", "phase-7"],
    description: `**Audit immutability:** Partial fix shipped (\`20260708130000_audit_retention_and_immutability.sql\`) — member RLS read-only; \`retention_purge()\` still deletes aged events.

**Pack rollback:** Per-asset versions only; no coordinated pack-level rollback.

**Blocking for compliance-heavy approval trails:** retention purge behavior.`,
  },
  {
    key: "7.3",
    title: "[MKT-PACK-AUDIT 7.3] Usage analytics — partial batch + hours saved",
    labels: ["marketing-pack-audit", "phase-7"],
    description: `**Partial batch outcomes:** Not representable in current analytics schema.

**Hours saved:** \`estimated_hours_saved\` on marketplace assets remains estimate-only (\`marketplace/roi.py\`); no measured-vs-estimate distinction for packs.`,
  },
  {
    key: "discrepancy",
    title: "[MKT-PACK-AUDIT] Post-consolidation discrepancies vs expected state",
    labels: ["marketing-pack-audit", "platform-audit"],
    description: `Discrepancies found (link to original Phase 1–4 / AI-agentic tickets):

1. **CoordinationLayer KILLED** (2026-06-21) — not cut over. \`docs/delivery/sta258-coordination-evaluation-latest.json\` (STA-258)
2. **ExecutionCore** — implemented as \`AgentIntelligence\`, not a class named ExecutionCore (STA-284 area)
3. **Audit retention** — \`retention_purge()\` still deletes; RLS write gap fixed
4. **Connector count** — 19 OAuth providers, 62 catalog vendors (not ~19 total)
5. **Linear execute path** — graph canonical; linear workflow path still separate`,
  },
  {
    key: "7.4-reuse",
    title: "[MKT-PACK-AUDIT 7.4] Reusability — build general primitives for future packs",
    labels: ["marketing-pack-audit", "reusability"],
    description: `Build as general-purpose (HR/Finance/Operations/Sales):

- Mode A/B feedback toggle (especially)
- Batch + partial approval
- Rejection → upstream routing
- Pack tier pricing framework (done — \`pack_pricing.py\`, one-time \`paid\`)
- One-time entitlement path (done)

Marketing-specific: LinkedIn publish, post-publish engagement metrics wiring.`,
  },
  {
    key: "8.3-framework",
    title: "[MKT-PACK PRICING] Department Pack Pricing Framework (general reference)",
    labels: ["marketing-pack-audit", "pricing", "marketplace"],
    description: `**General pricing reference for all department packs** — do not re-derive per pack.

**Model:** One-time unlock (\`paid\`) — platform subscription + AI usage billed separately
**Tiers:** 1=$49, 2=$149, 3=$299 (USD one-time)
**Eligibility:** Control + Command tiers (Node must upgrade)

**Research:** Make Teams ~$29/user, Zapier Team ~$69/mo, Jasper Pro $69/seat (June 2026)

**Codified:** \`backend/app/marketplace/pack_pricing.py\`, migration \`20260709120000_marketplace_pack_tier.sql\`

**Mode B pricing:** Pending product sign-off (included + risk gate vs +$49 add-on)

**Doc:** \`docs/delivery/MARKETING_OPS_PACK_PHASE5-8_AUDIT.md\``,
  },
  {
    key: "8.5-impl",
    title: "[MKT-PACK PRICING] Marketing Operations Pack — $149 one-time Stripe checkout live",
    labels: ["marketing-pack-audit", "pricing", "marketplace"],
    description: `**Price:** $149 one-time unlock (14900 cents)
**Tier:** 2
**Slug:** marketing-operations-pack
**Billing split:** Platform Node/Control/Command = monthly subscription; AI usage = metered; pack = one-time paid unlock

**Implementation:**
- Migration \`20260709120000_marketplace_pack_tier.sql\` + \`20260709130000_department_pack_one_time_pricing.sql\`
- Seed \`seed_catalog.py\` + \`seed_service.py\`
- Checkout via existing \`create_asset_checkout_session()\` (payment mode, not subscription)
- Tests: \`test_department_pack_pricing.py\`

**Live verification:** POST install without entitlement → 402 PAYMENT_REQUIRED; Stripe Checkout one-time payment for $149.`,
  },
];

async function main() {
  const apiKey = getApiKey();
  if (!apiKey) {
    console.error(`
No Linear auth found.

Option A (Railway key — recommended):
  railway login
  railway link
  npm run linear:marketing-pack-audit

Option B (local env):
  $env:LINEAR_API_KEY="lin_api_..."
  node scripts/create-marketing-pack-audit-linear-issues.mjs
`);
    process.exit(1);
  }

  console.log("Creating Marketing Operations Pack audit tickets in Linear...\n");
  const team = await getTeam(apiKey);
  const labelCache = new Map((team.labels?.nodes || []).map((l) => [l.name, l.id]));
  const allLabelNames = [...new Set(ISSUES.flatMap((i) => i.labels || []))];
  for (const name of allLabelNames) {
    const id = await ensureLabel(apiKey, team.id, name, [...labelCache.entries()].map(([n, i]) => ({ name: n, id: i })));
    labelCache.set(name, id);
  }

  const created = {};
  for (const issue of ISSUES) {
    const labelIds = (issue.labels || []).map((n) => labelCache.get(n)).filter(Boolean);
    created[issue.key] = await createIssue(apiKey, team.id, labelIds, issue);
  }

  console.log("\n--- Ticket IDs by category ---");
  console.log(
    "Phase 5–7 sections:",
    ["5.1", "5.2", "6.1", "6.2", "7.1", "7.2", "7.3"].map((k) => `${k}=${created[k]}`).join(", "),
  );
  console.log("Mode A/B decision:", created["6.2-decision"]);
  console.log("Discrepancy:", created.discrepancy);
  console.log("Reusability:", created["7.4-reuse"]);
  console.log("Pricing framework:", created["8.3-framework"]);
  console.log("Mkt Ops Stripe impl:", created["8.5-impl"]);
}

main().catch((err) => {
  console.error(err.message || err);
  process.exit(1);
});
