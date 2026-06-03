#!/usr/bin/env node
/**
 * Create Tier 5 Integration Platform issues in Linear (18-month wave).
 *
 * Usage:
 *   $env:LINEAR_API_KEY="lin_api_..."
 *   npm run linear:tier5
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
  handoffBus: "STA-17",
  hubspotActions: "STA-15",
};
const T4 = {
  piiRedaction: "STA-82",
  workflowQueue: "STA-94",
  modelPolicy: "STA-90",
  workforceAnalytics: "STA-91",
};

const EPICS = [
  {
    key: "epic-a",
    title: "[Epic A] Autonomous Execution & Guardrails (Tier 5)",
    description: `Move beyond plan-only agents to policy-gated auto-execute with rollback and budgets.

**Closes audit gap:** \`agent_jobs.py\` "Never auto-execute"

**Child issues:** T5-001 through T5-004

**Requires:** ${T1.invokeTool}, ${T1.permissions}, ${T4.modelPolicy}`,
    labels: ["tier-5", "agents", "platform"],
    estimate: 21,
  },
  {
    key: "epic-b",
    title: "[Epic B] Regulated Industry Compliance (Tier 5)",
    description: `HIPAA, FedRAMP prep, EU AI Act decision transparency.

**Child issues:** T5-005 through T5-007

**Requires:** ${T4.piiRedaction}, STA-81 SOC2 export`,
    labels: ["tier-5", "compliance", "security"],
    estimate: 16,
  },
  {
    key: "epic-c",
    title: "[Epic C] Industry Vertical Packs (Tier 5)",
    description: `Pre-built agent roles, connectors, and workflows per vertical.

**Child issues:** T5-008 through T5-010`,
    labels: ["tier-5", "verticals", "integrations"],
    estimate: 16,
  },
  {
    key: "epic-d",
    title: "[Epic D] Multi-Org Federation & B2B Agents (Tier 5)",
    description: `Cross-organization agent handoffs and delegated work between Gravitre tenants.

**Child issues:** T5-011 through T5-013

**Requires:** ${T1.handoffBus}, STA-86 SSO`,
    labels: ["tier-5", "platform", "enterprise"],
    estimate: 16,
  },
  {
    key: "epic-e",
    title: "[Epic E] Advanced AI Workforce (Tier 5)",
    description: `Swarms, simulation, agent onboarding marketplace.

**Child issues:** T5-014 through T5-016`,
    labels: ["tier-5", "agents", "ai"],
    estimate: 16,
  },
  {
    key: "epic-f",
    title: "[Epic F] Platform Intelligence (Tier 5)",
    description: `Predictive ops, auto-recommendations, customer health scoring.

**Child issues:** T5-017 through T5-019

**Requires:** ${T4.workforceAnalytics}`,
    labels: ["tier-5", "platform", "analytics"],
    estimate: 13,
  },
];

const ISSUES = [
  {
    id: "T5-001",
    epic: "epic-a",
    title: "Policy-gated auto-execute mode per agent",
    priority: 2,
    estimate: 8,
    labels: ["tier-5", "agents", "platform"],
    description: `## Goal
Agents execute approved tool plans without human click-through when policy allows.

## Acceptance criteria
- [ ] Per-agent mode: plan-only | auto-with-approval | auto-trusted-scopes
- [ ] Overrides \`_OPERATOR_SYSTEM_PROMPT\` never-auto-execute when enabled
- [ ] Audit: who enabled, when, scope snapshot

## Depends on
${T1.invokeTool}, ${T1.permissions}, ${T4.modelPolicy}`,
  },
  {
    id: "T5-002",
    epic: "epic-a",
    title: "Compensating transactions / rollback for tool actions",
    priority: 2,
    estimate: 8,
    labels: ["tier-5", "agents", "platform"],
    description: `## Goal
When auto-execute fails mid-workflow, reverse or compensate CRM/ticket writes where vendor API supports it.

## V1
HubSpot + Zendesk undo patterns; webhook notify on partial failure`,
  },
  {
    id: "T5-003",
    epic: "epic-a",
    title: "Real-time human-in-the-loop interrupt channel",
    priority: 2,
    estimate: 5,
    labels: ["tier-5", "agents", "frontend"],
    description: `## Goal
Operator can pause/cancel running agent task from UI; agent receives interrupt before next tool call.

## Channels
In-app + Slack slash command`,
  },
  {
    id: "T5-004",
    epic: "epic-a",
    title: "Autonomous run budgets (tokens, actions, spend/day)",
    priority: 2,
    estimate: 5,
    labels: ["tier-5", "agents", "billing"],
    description: `## Goal
Hard caps per agent/org on auto-execute: max tool calls, LLM tokens, estimated USD.

## Ties to
STA-92 cost attribution`,
  },
  {
    id: "T5-005",
    epic: "epic-b",
    title: "HIPAA BAA workflow + PHI handling controls",
    priority: 3,
    estimate: 8,
    labels: ["tier-5", "compliance", "healthcare"],
    description: `## Deliverable
BAA acceptance flow, PHI-tagged connectors, blocked tools in non-HIPAA mode

## Requires
${T4.piiRedaction}, STA-80 data residency`,
  },
  {
    id: "T5-006",
    epic: "epic-b",
    title: "FedRAMP Moderate — control gap assessment & roadmap",
    priority: 4,
    estimate: 5,
    labels: ["tier-5", "compliance", "security"],
    description: `## Deliverable
\`docs/compliance/fedramp-gap-analysis.md\` mapped to STA-81 evidence exports

## Not full certification — readiness documentation`,
  },
  {
    id: "T5-007",
    epic: "epic-b",
    title: "EU AI Act — agent decision transparency logs",
    priority: 3,
    estimate: 5,
    labels: ["tier-5", "compliance", "agents"],
    description: `## Goal
Exportable record: input context, model, tools invoked, human override, outcome per automated decision`,
  },
  {
    id: "T5-008",
    epic: "epic-c",
    title: "Healthcare vertical pack (FHIR read + prior-auth template)",
    priority: 3,
    estimate: 8,
    labels: ["tier-5", "verticals", "healthcare"],
    description: `## Includes
- FHIR patient/appointment read (sandbox)
- CS + clinical admin agent templates
- Workflow: referral → prior auth checklist

## Depends on
T5-005 HIPAA controls`,
  },
  {
    id: "T5-009",
    epic: "epic-c",
    title: "Legal vertical pack (Clio + matter workflows)",
    priority: 3,
    estimate: 8,
    labels: ["tier-5", "verticals", "legal"],
    description: `## Includes
- Clio OAuth + matter/contact read (v1)
- Intake → conflict check → task assignment template`,
  },
  {
    id: "T5-010",
    epic: "epic-c",
    title: "Real estate vertical pack (CRM + listing workflow)",
    priority: 4,
    estimate: 5,
    labels: ["tier-5", "verticals", "integrations"],
    description: `## Includes
- Template: new listing → MLS note → buyer agent handoff
- Reuse HubSpot/Salesforce from Tier 1–2`,
  },
  {
    id: "T5-011",
    epic: "epic-d",
    title: "Cross-org agent handoff protocol (B2B briefing exchange)",
    priority: 3,
    estimate: 8,
    labels: ["tier-5", "platform", "enterprise"],
    description: `## Goal
Org A Sales Agent hands briefing to Org B partner agent with mutual consent + audit.

## Extends
${T1.handoffBus}`,
  },
  {
    id: "T5-012",
    epic: "epic-d",
    title: "Federated connector consent (share tool access across orgs)",
    priority: 4,
    estimate: 5,
    labels: ["tier-5", "platform", "security"],
    description: `## Goal
Partner org grants read-only CRM slice to your agents via time-boxed token`,
  },
  {
    id: "T5-013",
    epic: "epic-d",
    title: "Delegate task to external Gravitre org",
    priority: 3,
    estimate: 5,
    labels: ["tier-5", "platform", "agents"],
    description: `## Demo
Prime contractor delegates sub-task to subcontractor org; status syncs back`,
  },
  {
    id: "T5-014",
    epic: "epic-e",
    title: "Multi-agent swarm coordinator",
    priority: 3,
    estimate: 8,
    labels: ["tier-5", "agents", "ai"],
    description: `## Goal
Parent agent spawns N sub-agents with scoped tools; aggregates results with council pattern

## Key files
\`council_service.py\`, agent_jobs queue`,
  },
  {
    id: "T5-015",
    epic: "epic-e",
    title: "Workflow digital twin — simulate before live run",
    priority: 3,
    estimate: 8,
    labels: ["tier-5", "workflows", "ai"],
    description: `## Goal
Dry-run uses recorded connector fixtures + LLM to predict outcomes; no side effects

## Extends
\`dry_run.py\``,
  },
  {
    id: "T5-016",
    epic: "epic-e",
    title: "Agent role marketplace (install department packs)",
    priority: 3,
    estimate: 5,
    labels: ["tier-5", "agents", "marketplace"],
    description: `## Goal
One-click install: agents + RAG sources + workflows + connector requirements checklist

## Ties to
STA-73 marketplace demo`,
  },
  {
    id: "T5-017",
    epic: "epic-f",
    title: "Predictive workflow failure detection",
    priority: 3,
    estimate: 5,
    labels: ["tier-5", "platform", "analytics"],
    description: `## Goal
ML/heuristic alerts before step fails (auth expiry, rate limit trend, missing scope)`,
  },
  {
    id: "T5-018",
    epic: "epic-f",
    title: "Auto-suggest connectors & workflows from audit data",
    priority: 4,
    estimate: 5,
    labels: ["tier-5", "platform", "analytics"],
    description: `## Goal
"You run 40% of tasks manually in HubSpot — enable STA-15 actions" style recommendations`,
  },
  {
    id: "T5-019",
    epic: "epic-f",
    title: "Customer integration health score (CS dashboard)",
    priority: 3,
    estimate: 5,
    labels: ["tier-5", "analytics", "enterprise"],
    description: `## Metrics
Connectors live, workflow success rate, agent utilization, approval latency

## Depends on
${T4.workforceAnalytics}`,
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
        `${LINEAR} label create -n ${shQuote(name)} -t ${shQuote(team)} -c "#1ABC9C"`,
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
  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "linear-tier5-"));
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
    console.error(`\n❌ LINEAR_API_KEY is not set.\n   npm run linear:tier5\n`);
    process.exit(1);
  }

  console.log("🔐 Using LINEAR_API_KEY from environment...");
  process.env.LINEAR_API_KEY = API_KEY;

  const team = process.env.LINEAR_TEAM || "STA";
  const targetDate = new Date();
  targetDate.setDate(targetDate.getDate() + 540);
  const targetDateStr = targetDate.toISOString().slice(0, 10);

  const initiativeName = "Tier 5 — Autonomous Workforce & Vertical Scale (18 months)";
  const projectName = "Tier 5 Integration Platform";

  console.log("📋 Creating initiative...");
  try {
    run(
      `${LINEAR} initiative create -n ${shQuote(initiativeName)} -s planned --target-date ${targetDateStr} -d ${shQuote("Auto-execute agents, regulated verticals, B2B federation, swarms, platform intelligence. Requires Tier 1–4.")}`,
      { capture: true },
    );
  } catch (e) {
    console.warn("   ⚠ Initiative:", e.message.split("\n")[0]);
  }

  console.log("📁 Creating project...");
  try {
    run(
      `${LINEAR} project create -n ${shQuote(projectName)} -t ${shQuote(team)} -s planned --target-date ${targetDateStr} --initiative ${shQuote(initiativeName)} -d ${shQuote("18-month vision: staffed AI-native business at scale.")}`,
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

  const outPath = path.join(__dirname, "..", "docs", "integration", "tier5-linear-ids.json");
  fs.mkdirSync(path.dirname(outPath), { recursive: true });
  fs.writeFileSync(
    outPath,
    JSON.stringify({ createdAt: new Date().toISOString(), epics: epicIds, issues: created }, null, 2),
  );

  console.log("\n✅ Done! Created 6 epics + 19 issues.\n");
  console.log("| Ref | Linear | Title | Epic |");
  console.log("|-----|--------|-------|------|");
  for (const row of created) {
    console.log(`| ${row.ref} | ${row.linear} | ${row.title} | ${row.parent} |`);
  }
  console.log(`\n📄 IDs saved to docs/integration/tier5-linear-ids.json`);
  console.log(`🔗 https://linear.app/${WORKSPACE}`);
}

main();
