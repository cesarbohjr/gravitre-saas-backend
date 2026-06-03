#!/usr/bin/env node
/**
 * Create Tier 4 Integration Platform issues in Linear (12-month wave).
 *
 * Usage:
 *   $env:LINEAR_API_KEY="lin_api_..."
 *   npm run linear:tier4
 *
 * Prerequisites: Tier 1–3 — see docs/integration/LINEAR_INTEGRATION_BACKLOG.md
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

const T1 = { invokeTool: "STA-10", permissions: "STA-11", audit: "STA-10" };
const T3 = { marketplaceSdk: "STA-70", marketplaceDemo: "STA-73" };

const EPICS = [
  {
    key: "epic-a",
    title: "[Epic A] Enterprise Security & Compliance (Tier 4)",
    description: `SOC2 evidence, PII handling, SIEM export, data residency.

**Child issues:** T4-001 through T4-004

**Requires:** ${T1.invokeTool} audit trail`,
    labels: ["tier-4", "security", "compliance"],
    estimate: 16,
  },
  {
    key: "epic-b",
    title: "[Epic B] Enterprise Deploy & Identity (Tier 4)",
    description: `White-label, VPC/single-tenant, SAML/OIDC for operators.

**Child issues:** T4-005 through T4-007`,
    labels: ["tier-4", "enterprise", "platform"],
    estimate: 13,
  },
  {
    key: "epic-c",
    title: "[Epic C] Extended HR & Finance Connectors (Tier 4)",
    description: `BambooHR, Greenhouse, Xero — departments not covered in Tier 2–3.

**Child issues:** T4-008 through T4-010`,
    labels: ["tier-4", "integrations"],
    estimate: 11,
  },
  {
    key: "epic-d",
    title: "[Epic D] AI Governance & Workforce Analytics (Tier 4)",
    description: `Model policy, agent KPIs, cost attribution per agent/org.

**Child issues:** T4-011 through T4-013`,
    labels: ["tier-4", "agents", "platform"],
    estimate: 13,
  },
  {
    key: "epic-e",
    title: "[Epic E] Global Scale & Reliability (Tier 4)",
    description: `Multi-region execution, workflow queue HA, disaster recovery.

**Child issues:** T4-014 through T4-016`,
    labels: ["tier-4", "infrastructure"],
    estimate: 16,
  },
  {
    key: "epic-f",
    title: "[Epic F] Marketplace & Ecosystem Scale (Tier 4)",
    description: `Marketplace v2, partner certification, private connector runtime.

**Child issues:** T4-017 through T4-020

**Requires:** ${T3.marketplaceSdk}, ${T3.marketplaceDemo}`,
    labels: ["tier-4", "marketplace"],
    estimate: 16,
  },
];

const ISSUES = [
  {
    id: "T4-001",
    epic: "epic-a",
    title: "Data residency — region-pinned org storage",
    priority: 3,
    estimate: 8,
    labels: ["tier-4", "compliance", "platform"],
    description: `## Goal
Enterprise customers choose data region (US/EU); RAG + secrets + audit stay in region.

## Acceptance criteria
- [ ] org.data_region column + enforcement in Supabase RLS / storage paths
- [ ] Connector tokens not replicated cross-region
- [ ] Admin UI region selector at org creation`,
  },
  {
    id: "T4-002",
    epic: "epic-a",
    title: "SOC2 control mapping + compliance evidence export API",
    priority: 3,
    estimate: 5,
    labels: ["tier-4", "compliance", "security"],
    description: `## Deliverable
Exportable audit bundles: tool invocations, approvals, admin actions, connector changes.

## Maps to
Existing workflow audit (\`workflows/constants.py\`) + ${T1.invokeTool} logs`,
  },
  {
    id: "T4-003",
    epic: "epic-a",
    title: "PII detection & redaction in tool I/O audit stream",
    priority: 3,
    estimate: 5,
    labels: ["tier-4", "security", "platform"],
    description: `## Goal
Hash/redact emails, SSN patterns, credit cards in audit before persistence.

## Acceptance criteria
- [ ] Configurable per org (strict / standard)
- [ ] Raw PII never in SIEM export by default`,
  },
  {
    id: "T4-004",
    epic: "epic-a",
    title: "SIEM export (Splunk / Datadog / webhook)",
    priority: 4,
    estimate: 5,
    labels: ["tier-4", "security", "integration"],
    description: `## V1
- Streaming audit events to customer SIEM endpoint
- HMAC-signed payloads; retry with dead-letter queue`,
  },
  {
    id: "T4-005",
    epic: "epic-b",
    title: "White-label branding (domain, logo, email templates)",
    priority: 3,
    estimate: 5,
    labels: ["tier-4", "enterprise", "frontend"],
    description: `## Scope
- Custom subdomain (CNAME)
- Logo + primary color in app shell + transactional email
- "Powered by Gravitre" optional removal on enterprise plan`,
  },
  {
    id: "T4-006",
    epic: "epic-b",
    title: "Single-tenant / VPC deployment (Helm + runbook)",
    priority: 3,
    estimate: 8,
    labels: ["tier-4", "enterprise", "infrastructure"],
    description: `## Deliverable
\`deploy/enterprise/\` Helm chart: web + API + workers + Supabase-compatible Postgres option

## Includes
Security hardening checklist, secret rotation guide`,
  },
  {
    id: "T4-007",
    epic: "epic-b",
    title: "Enterprise SSO (SAML/OIDC) for operators & admins",
    priority: 2,
    estimate: 5,
    labels: ["tier-4", "enterprise", "auth"],
    description: `## Goal
Okta/Azure AD login for human operators; SCIM user provision (stretch).

## Key files
Supabase auth / middleware patterns in \`apps/web\``,
  },
  {
    id: "T4-008",
    epic: "epic-c",
    title: "BambooHR OAuth + v1 read actions",
    priority: 4,
    estimate: 5,
    labels: ["tier-4", "hr", "integration"],
    description: `## V1 actions
- bamboohr.employees.get
- bamboohr.timeoff.requests.list
- bamboohr.reports.run (headcount)

## Agent
HR Agent onboarding + PTO policy Q&A`,
  },
  {
    id: "T4-009",
    epic: "epic-c",
    title: "Greenhouse OAuth + recruiting pipeline read",
    priority: 4,
    estimate: 5,
    labels: ["tier-4", "hr", "integration"],
    description: `## V1 actions
- greenhouse.candidates.get
- greenhouse.applications.list
- greenhouse.jobs.list (open roles)`,
  },
  {
    id: "T4-010",
    epic: "epic-c",
    title: "Xero OAuth + accounting read (complement QuickBooks)",
    priority: 4,
    estimate: 5,
    labels: ["tier-4", "finance", "integration"],
    description: `## V1 actions
Mirror STA-34 QuickBooks scope for Xero API.

## Depends on
Tier 2 ${T1.invokeTool} pattern, STA-33/34 as reference`,
  },
  {
    id: "T4-011",
    epic: "epic-d",
    title: "Org model allowlist / blocklist policy engine",
    priority: 3,
    estimate: 5,
    labels: ["tier-4", "agents", "security"],
    description: `## Goal
Enterprise admins restrict which LLM providers/models agents may use.

## Extends
\`model_router.py\`, \`policy/engine.py\``,
  },
  {
    id: "T4-012",
    epic: "epic-d",
    title: "Agent workforce analytics dashboard",
    priority: 3,
    estimate: 8,
    labels: ["tier-4", "agents", "frontend"],
    description: `## Metrics
Tasks completed, handoffs, tool success rate, approval wait time, SLA breaches

## Data sources
agent_jobs, workflow audit, invoke_tool logs`,
  },
  {
    id: "T4-013",
    epic: "epic-d",
    title: "Per-agent cost attribution (LLM + connector API)",
    priority: 3,
    estimate: 5,
    labels: ["tier-4", "agents", "billing"],
    description: `## Goal
Finance/ops sees cost per agent, department, workflow.

## Ties to
Existing Stripe metering (\`billing/\`)`,
  },
  {
    id: "T4-014",
    epic: "epic-e",
    title: "Multi-region workflow execution routing",
    priority: 3,
    estimate: 8,
    labels: ["tier-4", "infrastructure", "workflows"],
    description: `## Goal
Runs execute in org's data region; cross-region only for read replicas.

## Depends on
T4-001 data residency`,
  },
  {
    id: "T4-015",
    epic: "epic-e",
    title: "Durable workflow run queue (HA worker pool)",
    priority: 2,
    estimate: 8,
    labels: ["tier-4", "infrastructure", "workflows"],
    description: `## Problem
Long-running / scheduled workflows need crash-safe queue beyond in-process execution.

## Acceptance criteria
- [ ] Redis or SQS-backed queue abstraction
- [ ] At-least-once delivery + idempotent step keys`,
  },
  {
    id: "T4-016",
    epic: "epic-e",
    title: "Workflow engine disaster recovery runbook + drills",
    priority: 4,
    estimate: 3,
    labels: ["tier-4", "infrastructure"],
    description: `## Deliverable
RPO/RTO targets, backup/restore for workflow definitions + run state, quarterly drill checklist`,
  },
  {
    id: "T4-017",
    epic: "epic-f",
    title: "Marketplace v2 — partner revenue share & billing",
    priority: 4,
    estimate: 8,
    labels: ["tier-4", "marketplace", "billing"],
    description: `## Goal
Partners set connector pricing; Gravitre collects and remits share.

## Depends on
${T3.marketplaceDemo}, Stripe Connect patterns`,
  },
  {
    id: "T4-018",
    epic: "epic-f",
    title: "Certified partner program + automated security review",
    priority: 4,
    estimate: 5,
    labels: ["tier-4", "marketplace", "security"],
    description: `## Includes
Static analysis on submitted packages, permission scope review, badge in registry`,
  },
  {
    id: "T4-019",
    epic: "epic-f",
    title: "Customer private connector runtime (signed packages)",
    priority: 3,
    estimate: 8,
    labels: ["tier-4", "marketplace", "platform"],
    description: `## Goal
Enterprise uploads signed connector bundle; runs in isolated worker sandbox.

## Depends on
${T3.marketplaceSdk}, T4-006 VPC option`,
  },
  {
    id: "T4-020",
    epic: "epic-f",
    title: "Fine-tuning pipeline wired to agent runtime",
    priority: 4,
    estimate: 8,
    labels: ["tier-4", "agents", "platform"],
    description: `## Problem
\`training.py\` / training entities exist but are not wired to agent inference.

## Acceptance criteria
- [ ] Org can assign fine-tuned model to specific agent
- [ ] Fallback to base model on failure
- [ ] Audit log of model version per task`,
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
        `${LINEAR} label create -n ${shQuote(name)} -t ${shQuote(team)} -c "#E67E22"`,
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
  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "linear-tier4-"));
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
   npm run linear:tier4
`);
    process.exit(1);
  }

  console.log("🔐 Using LINEAR_API_KEY from environment...");
  process.env.LINEAR_API_KEY = API_KEY;

  const team = process.env.LINEAR_TEAM || "STA";
  const targetDate = new Date();
  targetDate.setDate(targetDate.getDate() + 365);
  const targetDateStr = targetDate.toISOString().slice(0, 10);

  const initiativeName = "Tier 4 — Enterprise Scale & Ecosystem (12 months)";
  const projectName = "Tier 4 Integration Platform";

  console.log("📋 Creating initiative...");
  try {
    run(
      `${LINEAR} initiative create -n ${shQuote(initiativeName)} -s planned --target-date ${targetDateStr} -d ${shQuote("Compliance, white-label/VPC, extended connectors, AI governance, HA, marketplace v2. Requires Tier 1–3.")}`,
      { capture: true },
    );
  } catch (e) {
    console.warn("   ⚠ Initiative:", e.message.split("\n")[0]);
  }

  console.log("📁 Creating project...");
  try {
    run(
      `${LINEAR} project create -n ${shQuote(projectName)} -t ${shQuote(team)} -s planned --target-date ${targetDateStr} --initiative ${shQuote(initiativeName)} -d ${shQuote("12-month enterprise readiness and ecosystem scale.")}`,
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

  const outPath = path.join(__dirname, "..", "docs", "integration", "tier4-linear-ids.json");
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
  console.log(`\n📄 IDs saved to docs/integration/tier4-linear-ids.json`);
  console.log(`🔗 https://linear.app/${WORKSPACE}`);
}

main();
