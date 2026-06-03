#!/usr/bin/env node
/**
 * Create Tier 2 Integration Platform issues in Linear (90-day wave).
 *
 * Usage:
 *   $env:LINEAR_API_KEY="lin_api_..."
 *   $env:LINEAR_TEAM="STA"
 *   npm run linear:tier2
 *
 * Prerequisite: Tier 1 complete (invoke_tool, HubSpot, handoffs) — see docs/integration/LINEAR_INTEGRATION_BACKLOG.md
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
const API_KEY = process.env.LINEAR_API_KEY || process.env.LINEAR_TOKEN;

const T1 = {
  invokeTool: "STA-10",
  permissions: "STA-11",
  mergeEngines: "STA-12",
  oauthUx: "STA-13",
  hubspotOAuth: "STA-14",
  hubspotActions: "STA-15",
  handoffBus: "STA-17",
  deptRag: "STA-20",
};

const EPICS = [
  {
    key: "epic-a",
    title: "[Epic A] Salesforce CRM (Tier 2)",
    description: `Enterprise CRM for Sales Agent customers on Salesforce.

**Child issues:** T2-001 through T2-003

**Requires Tier 1:** ${T1.invokeTool}, ${T1.permissions}, ${T1.oauthUx}`,
    labels: ["tier-2", "salesforce"],
    estimate: 13,
  },
  {
    key: "epic-b",
    title: "[Epic B] Finance & Accounting (Tier 2)",
    description: `QuickBooks/Xero + Stripe read-only agent tools for Finance Agent.

**Child issues:** T2-004 through T2-006

**Requires Tier 1:** ${T1.invokeTool}, ${T1.permissions}`,
    labels: ["tier-2", "finance"],
    estimate: 11,
  },
  {
    key: "epic-c",
    title: "[Epic C] DevOps & Incidents (Tier 2)",
    description: `Jira + PagerDuty for Engineering/DevOps agents.

**Child issues:** T2-007 through T2-010

**Requires Tier 1:** ${T1.invokeTool}, ${T1.mergeEngines}`,
    labels: ["tier-2", "devops"],
    estimate: 13,
  },
  {
    key: "epic-d",
    title: "[Epic D] Marketing Analytics (Tier 2)",
    description: `Google Analytics for Marketing Agent attribution and reporting.

**Child issues:** T2-011 through T2-013

**Requires Tier 1:** ${T1.invokeTool}, ${T1.hubspotActions}`,
    labels: ["tier-2", "marketing"],
    estimate: 8,
  },
  {
    key: "epic-e",
    title: "[Epic E] Knowledge Sync Pipeline (Tier 2)",
    description: `Notion/Confluence → RAG; CRM/ticket incremental sync.

**Child issues:** T2-014 through T2-017

**Requires Tier 1:** ${T1.deptRag}, ${T1.hubspotActions}`,
    labels: ["tier-2", "rag"],
    estimate: 13,
  },
  {
    key: "epic-f",
    title: "[Epic F] Platform Maturity (Tier 2)",
    description: `Scheduled workflows, council branching, agent memory API.

**Child issues:** T2-018 through T2-020

**Requires Tier 1:** ${T1.mergeEngines}, ${T1.handoffBus}`,
    labels: ["tier-2", "platform"],
    estimate: 11,
  },
];

const ISSUES = [
  {
    id: "T2-001",
    epic: "epic-a",
    title: "Salesforce OAuth + token lifecycle",
    priority: 2,
    estimate: 3,
    labels: ["tier-2", "salesforce", "integration"],
    description: `## Goal
Connect Salesforce orgs via OAuth for Sales Agent workflows.

## Acceptance criteria
- [ ] OAuth2 connected app (sandbox + prod)
- [ ] Token refresh; encrypted storage
- [ ] Admin connects from connectors UI (reuse ${T1.oauthUx})

## Depends on Tier 1
${T1.invokeTool}, ${T1.oauthUx}`,
  },
  {
    id: "T2-002",
    epic: "epic-a",
    title: "Salesforce v1 actions",
    priority: 2,
    estimate: 5,
    labels: ["tier-2", "salesforce", "sales-agent"],
    description: `## V1 actions
- salesforce.leads.get / update
- salesforce.opportunities.create / update_stage
- salesforce.accounts.get
- salesforce.tasks.create (log activity)

## Demo
Inbound lead → update lead status → create opportunity

## Depends on Tier 1
${T1.invokeTool}, ${T1.permissions}`,
  },
  {
    id: "T2-003",
    epic: "epic-a",
    title: "Salesforce inbound triggers → workflows",
    priority: 3,
    estimate: 5,
    labels: ["tier-2", "salesforce", "workflows"],
    description: `## V1 triggers
- Lead.created
- Opportunity.stageChange

## Depends on Tier 1
${T1.mergeEngines}`,
  },
  {
    id: "T2-004",
    epic: "epic-b",
    title: "QuickBooks Online OAuth + token lifecycle",
    priority: 2,
    estimate: 3,
    labels: ["tier-2", "finance", "integration"],
    description: `## Goal
Finance Agent reads accounting data (v1: QuickBooks; Xero as follow-up issue if needed).

## Acceptance criteria
- [ ] Intuit OAuth; sandbox support
- [ ] Encrypted token storage
- [ ] Scope: accounting.readonly minimum

## Depends on Tier 1
${T1.invokeTool}, ${T1.oauthUx}`,
  },
  {
    id: "T2-005",
    epic: "epic-b",
    title: "QuickBooks v1 read actions",
    priority: 2,
    estimate: 5,
    labels: ["tier-2", "finance", "finance-agent"],
    description: `## V1 actions
- quickbooks.invoices.list / get
- quickbooks.payments.list
- quickbooks.vendors.get

## Demo
Finance Agent summarizes overdue invoices for approver Slack notify

## Depends on Tier 1
${T1.invokeTool}, ${T1.permissions}`,
  },
  {
    id: "T2-006",
    epic: "epic-b",
    title: "Stripe read-only agent tool",
    priority: 2,
    estimate: 3,
    labels: ["tier-2", "finance", "stripe"],
    description: `## Goal
Finance Agent reads subscription/invoice data (distinct from platform billing Stripe).

## V1 actions
- stripe.invoices.list (connected account or platform key per org config)
- stripe.subscriptions.get

## Key files
\`backend/app/billing/stripe.py\` (reuse patterns, separate agent tool path)

## Depends on Tier 1
${T1.invokeTool}`,
  },
  {
    id: "T2-007",
    epic: "epic-c",
    title: "Jira Cloud OAuth + v1 actions",
    priority: 2,
    estimate: 5,
    labels: ["tier-2", "jira", "devops-agent"],
    description: `## V1 actions
- jira.issues.create
- jira.issues.assign
- jira.issues.transition
- jira.issues.comment

## Trigger
jira:issue_created (stretch)

## Depends on Tier 1
${T1.invokeTool}, ${T1.oauthUx}`,
  },
  {
    id: "T2-008",
    epic: "epic-c",
    title: "PagerDuty OAuth + incident triggers",
    priority: 2,
    estimate: 3,
    labels: ["tier-2", "pagerduty", "devops-agent"],
    description: `## V1 triggers
- incident.triggered
- incident.acknowledged

## Workflow demo
PagerDuty alert → DevOps Agent creates Jira issue + Slack notify

## Depends on Tier 1
${T1.mergeEngines}`,
  },
  {
    id: "T2-009",
    epic: "epic-c",
    title: "PagerDuty v1 actions",
    priority: 2,
    estimate: 3,
    labels: ["tier-2", "pagerduty", "devops-agent"],
    description: `## V1 actions
- pagerduty.incidents.acknowledge
- pagerduty.incidents.add_note
- pagerduty.incidents.escalate

## Depends on Tier 1
${T1.invokeTool}`,
  },
  {
    id: "T2-010",
    epic: "epic-c",
    title: "Cross-tool DevOps workflow (PagerDuty + Jira + Slack)",
    priority: 3,
    estimate: 3,
    labels: ["tier-2", "devops", "workflows"],
    description: `## Goal
Ship one end-to-end operating procedure using Tier 1 Slack + Tier 2 Jira/PagerDuty.

## Demo
Incident triggered → Jira ticket + assignee → Slack #eng-alerts

## Depends on
T2-007, T2-008, T2-009, Tier 1 Slack steps`,
  },
  {
    id: "T2-011",
    epic: "epic-d",
    title: "Google Analytics OAuth + property linking",
    priority: 3,
    estimate: 3,
    labels: ["tier-2", "marketing", "google-analytics"],
    description: `## Goal
Marketing Agent reads campaign performance (GA4 Data API).

## Depends on Tier 1
${T1.oauthUx}, ${T1.invokeTool}`,
  },
  {
    id: "T2-012",
    epic: "epic-d",
    title: "GA4 v1 read actions",
    priority: 3,
    estimate: 5,
    labels: ["tier-2", "marketing", "google-analytics"],
    description: `## V1 actions
- analytics.reports.run (sessions, conversions by campaign)
- analytics.properties.list

## Demo
Weekly attribution summary posted to Slack`,
  },
  {
    id: "T2-013",
    epic: "epic-d",
    title: "Marketing attribution workflow template",
    priority: 3,
    estimate: 2,
    labels: ["tier-2", "marketing", "workflows"],
    description: `## Goal
Pre-built workflow: pull GA4 + HubSpot list → Marketing Agent summary → Slack.

## Depends on
T2-011, T2-012, ${T1.hubspotActions}`,
  },
  {
    id: "T2-014",
    epic: "epic-e",
    title: "Notion OAuth + workspace sync → RAG",
    priority: 2,
    estimate: 5,
    labels: ["tier-2", "notion", "rag"],
    description: `## Goal
Department playbooks in Notion sync to department-scoped RAG (${T1.deptRag}).

## Acceptance criteria
- [ ] OAuth; select pages/databases to sync
- [ ] Incremental ingest via existing \`rag/ingest.py\` pipeline
- [ ] Staleness indicator in admin UI

## Depends on Tier 1
${T1.deptRag}`,
  },
  {
    id: "T2-015",
    epic: "epic-e",
    title: "Confluence OAuth + space sync → RAG",
    priority: 3,
    estimate: 5,
    labels: ["tier-2", "confluence", "rag"],
    description: `## Goal
Confluence spaces sync to RAG namespaces (CS/Sales/HR SOPs).

## Trigger (stretch)
Webhook on page publish

## Depends on Tier 1
${T1.deptRag}`,
  },
  {
    id: "T2-016",
    epic: "epic-e",
    title: "Knowledge sync scheduler + webhook framework",
    priority: 2,
    estimate: 5,
    labels: ["tier-2", "rag", "platform"],
    description: `## Goal
Unified sync jobs: daily CRM/ticket pull + webhook-on-publish for docs.

## Acceptance criteria
- [ ] \`knowledge_sync_jobs\` table + worker
- [ ] Per-source schedule + last_synced_at
- [ ] Audit log of chunks added/updated

## Architecture ref
Audit §8.5 Knowledge Sync Pipeline`,
  },
  {
    id: "T2-017",
    epic: "epic-e",
    title: "HubSpot + Zendesk → RAG incremental sync",
    priority: 3,
    estimate: 5,
    labels: ["tier-2", "rag", "hubspot", "zendesk"],
    description: `## Goal
Sales/CS agents retrieve recent notes and resolved tickets in RAG context.

## Sources
- HubSpot notes/emails (daily)
- Zendesk resolved tickets (daily)

## Depends on Tier 1
${T1.hubspotActions}, Zendesk v1 (STA-21)`,
  },
  {
    id: "T2-018",
    epic: "epic-f",
    title: "Workflow schedule / cron trigger worker",
    priority: 2,
    estimate: 5,
    labels: ["tier-2", "workflows", "platform"],
    description: `## Problem
Schedule triggers have CRUD but no in-app cron worker (audit §5).

## Acceptance criteria
- [ ] Worker polls due schedules; starts workflow runs via merged executor
- [ ] Idempotency per schedule window
- [ ] Admin UI shows next run time

## Depends on Tier 1
${T1.mergeEngines}`,
  },
  {
    id: "T2-019",
    epic: "epic-f",
    title: "Council → workflow branch integration",
    priority: 3,
    estimate: 5,
    labels: ["tier-2", "platform", "agents"],
    description: `## Goal
Agents escalate ambiguous decisions to council; workflow branches on opinion.

## Key files
\`backend/app/services/council_service.py\`, \`decision_service.py\`

## Demo
Sales Agent uncertain lead score → council → branch enroll vs nurture

## Depends on Tier 1
${T1.handoffBus}, ${T1.mergeEngines}`,
  },
  {
    id: "T2-020",
    epic: "epic-f",
    title: "Agent memory API (replace mock UI)",
    priority: 3,
    estimate: 5,
    labels: ["tier-2", "agents", "rag"],
    description: `## Problem
\`agents/[id]/memory/page.tsx\` is mock data; no vector memory per agent.

## Acceptance criteria
- [ ] agent_memories table (org_id, agent_id, embedding, content, provenance)
- [ ] CRUD API + UI wired
- [ ] Task-time retrieval optional alongside department RAG

## Depends on Tier 1
${T1.deptRag}`,
  },
];

function ensureLabels(team) {
  const names = new Set();
  for (const epic of EPICS) epic.labels.forEach((l) => names.add(l));
  for (const issue of ISSUES) issue.labels.forEach((l) => names.add(l));

  console.log("🏷️  Ensuring labels...");
  for (const name of names) {
    try {
      run(
        `${LINEAR} label create -n ${shQuote(name)} -t ${shQuote(team)} -c "#7B61FF"`,
        { capture: true },
      );
      console.log(`   ✓ ${name}`);
    } catch (e) {
      const msg = e.message.toLowerCase();
      if (msg.includes("already") || msg.includes("duplicate") || msg.includes("exists")) {
        console.log(`   · ${name} (exists)`);
      } else {
        console.warn(`   ⚠ ${name}: ${e.message.split("\n")[0]}`);
      }
    }
  }
}

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

function createIssue({ title, description, team, parent, project, priority, estimate, labels }) {
  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "linear-tier2-"));
  const descFile = path.join(tmpDir, "desc.md");
  fs.writeFileSync(descFile, description, "utf-8");

  const parts = [
    LINEAR,
    "issue create",
    "--no-interactive",
    `-t ${shQuote(title)}`,
    `--description-file ${shQuote(descFile)}`,
    `--team ${shQuote(team)}`,
  ];
  if (parent) parts.push(`--parent ${shQuote(parent)}`);
  if (project) parts.push(`--project ${shQuote(project)}`);
  if (priority) parts.push(`-p ${priority}`);
  if (estimate) parts.push(`--estimate ${estimate}`);
  for (const label of labels ?? []) {
    parts.push(`-l ${shQuote(label)}`);
  }

  const output = run(parts.join(" "), { capture: true });
  fs.rmSync(tmpDir, { recursive: true, force: true });

  const id = parseIssueId(output);
  if (!id) throw new Error(`Could not parse issue id from output:\n${output}`);
  return id;
}

function main() {
  if (!API_KEY) {
    console.error(`
❌ LINEAR_API_KEY is not set.

   $env:LINEAR_API_KEY="lin_api_..."
   npm run linear:tier2
`);
    process.exit(1);
  }

  console.log("🔐 Using LINEAR_API_KEY from environment...");
  process.env.LINEAR_API_KEY = API_KEY;

  const team = process.env.LINEAR_TEAM || "STA";
  const targetDate = new Date();
  targetDate.setDate(targetDate.getDate() + 90);
  const targetDateStr = targetDate.toISOString().slice(0, 10);

  const initiativeName = "Tier 2 — Department Expansion (90 days)";
  const projectName = "Tier 2 Integration Platform";

  console.log("📋 Creating initiative...");
  try {
    run(
      `${LINEAR} initiative create -n ${shQuote(initiativeName)} -s planned --target-date ${targetDateStr} -d ${shQuote("Expand agent workforce: Salesforce, Finance, DevOps, Marketing analytics, knowledge sync. Builds on Tier 1 (STA-6–23).")}`,
      { capture: true },
    );
  } catch (e) {
    console.warn("   ⚠ Initiative:", e.message.split("\n")[0]);
  }

  console.log("📁 Creating project...");
  try {
    run(
      `${LINEAR} project create -n ${shQuote(projectName)} -t ${shQuote(team)} -s planned --target-date ${targetDateStr} --initiative ${shQuote(initiativeName)} -d ${shQuote("90-day integrations per Integration Platform Audit (May 2026).")}`,
      { capture: true },
    );
  } catch (e) {
    console.warn("   ⚠ Project:", e.message.split("\n")[0]);
  }

  ensureLabels(team);

  const epicIds = {};
  console.log("\n📦 Creating epics...");
  for (const epic of EPICS) {
    const id = createIssue({
      title: epic.title,
      description: epic.description,
      team,
      project: projectName,
      estimate: epic.estimate,
      labels: epic.labels,
      priority: 2,
    });
    epicIds[epic.key] = id;
    console.log(`   ✓ ${id}  ${epic.title}`);
  }

  console.log("\n📝 Creating issues...");
  const created = [];
  for (const issue of ISSUES) {
    const parent = epicIds[issue.epic];
    const id = createIssue({
      title: `[${issue.id}] ${issue.title}`,
      description: issue.description,
      team,
      project: projectName,
      parent,
      priority: issue.priority,
      estimate: issue.estimate,
      labels: issue.labels,
    });
    created.push({ ref: issue.id, linear: id, title: issue.title, parent });
    console.log(`   ✓ ${id}  [${issue.id}] ${issue.title}`);
  }

  const outPath = path.join(__dirname, "..", "docs", "integration", "tier2-linear-ids.json");
  fs.mkdirSync(path.dirname(outPath), { recursive: true });
  fs.writeFileSync(
    outPath,
    JSON.stringify({ createdAt: new Date().toISOString(), epics: epicIds, issues: created }, null, 2),
  );

  console.log("\n✅ Done! Created 6 epics + 20 issues.\n");
  console.log("| Ref | Linear | Title | Epic |");
  console.log("|-----|--------|-------|------|");
  for (const row of created) {
    console.log(`| ${row.ref} | ${row.linear} | ${row.title} | ${row.parent} |`);
  }
  console.log(`\n📄 IDs saved to docs/integration/tier2-linear-ids.json`);
  console.log(`🔗 https://linear.app/${WORKSPACE}`);
}

main();
