#!/usr/bin/env node
/**
 * Create Tier 3 Integration Platform issues in Linear (6-month wave).
 *
 * Usage:
 *   $env:LINEAR_API_KEY="lin_api_..."
 *   npm run linear:tier3
 *
 * Prerequisites: Tier 1 + Tier 2 platform patterns — see docs/integration/LINEAR_INTEGRATION_BACKLOG.md
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

const T1 = { invokeTool: "STA-10", permissions: "STA-11", oauthUx: "STA-13", deptRag: "STA-20" };
const T2 = { knowledgeSync: "STA-45", qbRead: "STA-34", marketplacePrep: "STA-45" };

const EPICS = [
  {
    key: "epic-a",
    title: "[Epic A] NetSuite ERP (Tier 3)",
    description: `Enterprise ERP for Finance Agent — revenue, orders, customers.

**Child issues:** T3-001 through T3-003

**Requires:** ${T1.invokeTool}, ${T1.permissions}, Tier 2 Finance track`,
    labels: ["tier-3", "netsuite", "finance"],
    estimate: 13,
  },
  {
    key: "epic-b",
    title: "[Epic B] Workday HRIS (Tier 3)",
    description: `HR Agent — org structure, policies, worker data.

**Child issues:** T3-004 through T3-006

**Requires:** ${T1.deptRag}, ${T2.knowledgeSync}`,
    labels: ["tier-3", "workday", "hr"],
    estimate: 13,
  },
  {
    key: "epic-c",
    title: "[Epic C] LinkedIn Sales Navigator (Tier 3)",
    description: `Sales Agent prospect research and enrichment.

**Child issues:** T3-007 through T3-008`,
    labels: ["tier-3", "linkedin", "sales-agent"],
    estimate: 8,
  },
  {
    key: "epic-d",
    title: "[Epic D] Marketo MAP (Tier 3)",
    description: `Enterprise marketing automation beyond HubSpot.

**Child issues:** T3-009 through T3-011`,
    labels: ["tier-3", "marketo", "marketing"],
    estimate: 11,
  },
  {
    key: "epic-e",
    title: "[Epic E] Segment CDP (Tier 3)",
    description: `Customer data platform — identify, track, route events to workflows.

**Child issues:** T3-012 through T3-014`,
    labels: ["tier-3", "segment", "platform"],
    estimate: 11,
  },
  {
    key: "epic-f",
    title: "[Epic F] Connector Marketplace (Tier 3)",
    description: `Partner-built connectors — SDK, review, sandbox.

**Child issues:** T3-015 through T3-018

**Requires:** ${T1.invokeTool}, ${T1.oauthUx}, ${T1.permissions}`,
    labels: ["tier-3", "marketplace", "platform"],
    estimate: 16,
  },
];

const ISSUES = [
  {
    id: "T3-001",
    epic: "epic-a",
    title: "NetSuite OAuth + token lifecycle (SuiteScript REST)",
    priority: 3,
    estimate: 5,
    labels: ["tier-3", "netsuite", "integration"],
    description: `## Goal
Connect NetSuite accounts (TBA / OAuth 2.0 per NetSuite docs).

## Acceptance criteria
- [ ] Sandbox + production credential flows
- [ ] Encrypted token storage; role-scoped tokens
- [ ] Admin connects from connectors UI

## Depends on
${T1.invokeTool}, ${T1.oauthUx}`,
  },
  {
    id: "T3-002",
    epic: "epic-a",
    title: "NetSuite v1 read actions",
    priority: 3,
    estimate: 5,
    labels: ["tier-3", "netsuite", "finance-agent"],
    description: `## V1 actions
- netsuite.customers.get
- netsuite.invoices.list / get
- netsuite.salesorders.get
- netsuite.items.get (catalog skim)

## Demo
Finance Agent weekly revenue summary → Slack`,
  },
  {
    id: "T3-003",
    epic: "epic-a",
    title: "NetSuite v1 write actions (controlled)",
    priority: 4,
    estimate: 5,
    labels: ["tier-3", "netsuite", "finance-agent"],
    description: `## V1 write (approval-gated)
- netsuite.journalentries.create (draft)
- netsuite.customers.update (billing contact only)

## Security
Requires ${T1.permissions} scope netsuite:write + workflow HUMAN_APPROVAL`,
  },
  {
    id: "T3-004",
    epic: "epic-b",
    title: "Workday OAuth + API integration",
    priority: 3,
    estimate: 5,
    labels: ["tier-3", "workday", "integration"],
    description: `## Goal
Workday REST/RaaS for HR Agent (read-heavy v1).

## Acceptance criteria
- [ ] OAuth / ISU credential pattern documented
- [ ] Encrypted credentials per org
- [ ] Sandbox tenant support`,
  },
  {
    id: "T3-005",
    epic: "epic-b",
    title: "Workday v1 read actions",
    priority: 3,
    estimate: 5,
    labels: ["tier-3", "workday", "hr"],
    description: `## V1 actions
- workday.workers.get (by email/id)
- workday.orgunits.list
- workday.timeoff.balance.get (read)
- workday.positions.list (open reqs skim)

## Demo
HR Agent answers "Who is my HR partner?" from Workday + RAG`,
  },
  {
    id: "T3-006",
    epic: "epic-b",
    title: "Workday policy docs → department RAG sync",
    priority: 3,
    estimate: 3,
    labels: ["tier-3", "workday", "rag"],
    description: `## Goal
HR department namespace auto-synced from Workday learning/policy sources.

## Depends on
${T1.deptRag}, ${T2.knowledgeSync}`,
  },
  {
    id: "T3-007",
    epic: "epic-c",
    title: "LinkedIn / Sales Navigator API evaluation + compliance",
    priority: 3,
    estimate: 3,
    labels: ["tier-3", "linkedin", "sales-agent"],
    description: `## Goal
Document approved API paths (Marketing API vs SN Partner Program), rate limits, ToS constraints.

## Deliverable
Architecture decision record in \`docs/integration/linkedin-sales-nav.md\`

## Outcome
Go/no-go for T3-008 implementation approach`,
  },
  {
    id: "T3-008",
    epic: "epic-c",
    title: "Sales Agent prospect enrichment action",
    priority: 3,
    estimate: 5,
    labels: ["tier-3", "linkedin", "sales-agent"],
    description: `## V1 action (post ADR)
- linkedin.prospect.enrich (company, title, mutual connections summary)

## Demo
Inbound lead → enrich → HubSpot note (requires Tier 1 HubSpot)

## Depends on
T3-007, Tier 1 HubSpot actions`,
  },
  {
    id: "T3-009",
    epic: "epic-d",
    title: "Marketo OAuth + instance linking",
    priority: 3,
    estimate: 3,
    labels: ["tier-3", "marketo", "integration"],
    description: `## Goal
Connect Marketo instances (REST + bulk export where needed).

## Depends on
${T1.oauthUx}, ${T1.invokeTool}`,
  },
  {
    id: "T3-010",
    epic: "epic-d",
    title: "Marketo v1 actions",
    priority: 3,
    estimate: 5,
    labels: ["tier-3", "marketo", "marketing"],
    description: `## V1 actions
- marketo.leads.get / update
- marketo.campaigns.list
- marketo.programs.status
- marketo.lists.add_to_static_list`,
  },
  {
    id: "T3-011",
    epic: "epic-d",
    title: "Enterprise nurture workflow templates (Marketo + handoffs)",
    priority: 4,
    estimate: 3,
    labels: ["tier-3", "marketo", "workflows"],
    description: `## Goal
Ship 2 templates: ABM handoff (Sales→Marketo program), webinar follow-up.

## Depends on
T3-010, Tier 1 handoff bus (STA-17)`,
  },
  {
    id: "T3-012",
    epic: "epic-e",
    title: "Segment source OAuth + workspace linking",
    priority: 3,
    estimate: 3,
    labels: ["tier-3", "segment", "integration"],
    description: `## Goal
Connect Segment workspace; store write key / OAuth per org securely.`,
  },
  {
    id: "T3-013",
    epic: "epic-e",
    title: "Segment v1 agent actions (identify + track)",
    priority: 3,
    estimate: 5,
    labels: ["tier-3", "segment", "platform"],
    description: `## V1 actions
- segment.identify
- segment.track
- segment.group (account-level)

## Use case
Agents emit structured product events for downstream analytics`,
  },
  {
    id: "T3-014",
    epic: "epic-e",
    title: "Segment → workflow trigger bridge",
    priority: 3,
    estimate: 5,
    labels: ["tier-3", "segment", "workflows"],
    description: `## Goal
Inbound Segment events (via Functions destination or webhook) start Gravitre workflows.

## Depends on
Tier 1 ${T1.invokeTool} execution path, Tier 2 schedule worker (STA-47) optional`,
  },
  {
    id: "T3-015",
    epic: "epic-f",
    title: "Connector SDK specification (manifest + handlers)",
    priority: 2,
    estimate: 5,
    labels: ["tier-3", "marketplace", "platform"],
    description: `## Deliverable
\`docs/integration/connector-sdk-spec.md\` + TypeScript/Python handler interface

## Includes
- manifest.json schema (oauth, actions, triggers)
- invoke_tool adapter contract
- Versioning + capability declarations`,
  },
  {
    id: "T3-016",
    epic: "epic-f",
    title: "Partner connector submission + review workflow",
    priority: 3,
    estimate: 5,
    labels: ["tier-3", "marketplace", "platform"],
    description: `## Acceptance criteria
- [ ] Admin UI: submit package, security checklist, approve/reject
- [ ] Audit log of reviewer actions
- [ ] Published connectors appear in registry`,
  },
  {
    id: "T3-017",
    epic: "epic-f",
    title: "Sandbox org for third-party connector testing",
    priority: 3,
    estimate: 5,
    labels: ["tier-3", "marketplace", "platform"],
    description: `## Goal
Isolated org template with demo agents + mock data for partner QA.

## Ties to
\`org_seed_service.py\` pattern`,
  },
  {
    id: "T3-018",
    epic: "epic-f",
    title: "Marketplace demo: partner-built connector in sandbox",
    priority: 3,
    estimate: 3,
    labels: ["tier-3", "marketplace", "integration"],
    description: `## Demo
Partner "Acme Tools" connector installs in sandbox → agent invokes one action → audit trail visible.

## Depends on
T3-015, T3-016, T3-017`,
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
        `${LINEAR} label create -n ${shQuote(name)} -t ${shQuote(team)} -c "#9B59B6"`,
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
  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "linear-tier3-"));
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
   npm run linear:tier3
`);
    process.exit(1);
  }

  console.log("🔐 Using LINEAR_API_KEY from environment...");
  process.env.LINEAR_API_KEY = API_KEY;

  const team = process.env.LINEAR_TEAM || "STA";
  const targetDate = new Date();
  targetDate.setDate(targetDate.getDate() + 180);
  const targetDateStr = targetDate.toISOString().slice(0, 10);

  const initiativeName = "Tier 3 — Enterprise & Marketplace (6 months)";
  const projectName = "Tier 3 Integration Platform";

  console.log("📋 Creating initiative...");
  try {
    run(
      `${LINEAR} initiative create -n ${shQuote(initiativeName)} -s planned --target-date ${targetDateStr} -d ${shQuote("NetSuite, Workday, LinkedIn SN, Marketo, Segment, connector marketplace. Requires Tier 1–2 platform.")}`,
      { capture: true },
    );
  } catch (e) {
    console.warn("   ⚠ Initiative:", e.message.split("\n")[0]);
  }

  console.log("📁 Creating project...");
  try {
    run(
      `${LINEAR} project create -n ${shQuote(projectName)} -t ${shQuote(team)} -s planned --target-date ${targetDateStr} --initiative ${shQuote(initiativeName)} -d ${shQuote("6-month enterprise integrations and partner connector ecosystem.")}`,
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
      priority: 3,
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

  const outPath = path.join(__dirname, "..", "docs", "integration", "tier3-linear-ids.json");
  fs.mkdirSync(path.dirname(outPath), { recursive: true });
  fs.writeFileSync(
    outPath,
    JSON.stringify({ createdAt: new Date().toISOString(), epics: epicIds, issues: created }, null, 2),
  );

  console.log("\n✅ Done! Created 6 epics + 18 issues.\n");
  console.log("| Ref | Linear | Title | Epic |");
  console.log("|-----|--------|-------|------|");
  for (const row of created) {
    console.log(`| ${row.ref} | ${row.linear} | ${row.title} | ${row.parent} |`);
  }
  console.log(`\n📄 IDs saved to docs/integration/tier3-linear-ids.json`);
  console.log(`🔗 https://linear.app/${WORKSPACE}`);
}

main();
