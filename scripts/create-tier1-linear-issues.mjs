#!/usr/bin/env node
/**
 * Create Tier 1 Integration Platform issues in Linear via @schpet/linear-cli.
 *
 * Usage:
 *   $env:LINEAR_API_KEY="lin_api_..."   # PowerShell
 *   $env:LINEAR_TEAM="STA"              # optional, auto-detected if omitted
 *   node scripts/create-tier1-linear-issues.mjs
 *
 * Get an API key: https://linear.app/settings/account/security
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
  // Avoid broken local install when repo path contains spaces.
  return "npx --yes --prefix %LOCALAPPDATA%\\linear-cli-tool @schpet/linear-cli";
}

function shQuote(value) {
  return `"${String(value).replace(/"/g, '\\"')}"`;
}

const LINEAR = resolveLinearCmd();
const WORKSPACE = process.env.LINEAR_WORKSPACE || "staqbot";
const API_KEY = process.env.LINEAR_API_KEY || process.env.LINEAR_TOKEN;

const EPICS = [
  {
    key: "epic-a",
    title: "[Epic A] Platform Foundation (Tier 1)",
    description: `Sprint 1 foundation work that unblocks every vendor integration.

**Goal:** Single audited tool execution path; webhook triggers use real connectors.

**Child issues:** T1-001 through T1-004`,
    labels: ["tier-1", "platform"],
    estimate: 16,
  },
  {
    key: "epic-b",
    title: "[Epic B] HubSpot CRM (Tier 1)",
    description: `HubSpot OAuth, 5 core actions, and inbound triggers.

**Demo target:** Seed workflow at \`backend/app/services/org_seed_service.py:89-100\`

**Child issues:** T1-005 through T1-007`,
    labels: ["tier-1", "hubspot"],
    estimate: 13,
  },
  {
    key: "epic-c",
    title: "[Epic C] Cross-Agent Orchestration (Tier 1)",
    description: `Handoff data bus, next_agent_id routing, workflow builder persistence.

**Child issues:** T1-008 through T1-010`,
    labels: ["tier-1", "agents"],
    estimate: 11,
  },
  {
    key: "epic-d",
    title: "[Epic D] Knowledge + Tier 1 Connectors",
    description: `Department-scoped RAG, Zendesk v1, GitHub v1, Calendar stretch.

**Child issues:** T1-011 through T1-014`,
    labels: ["tier-1", "integrations"],
    estimate: 16,
  },
];

const ISSUES = [
  {
    id: "T1-001",
    epic: "epic-a",
    title: "Unified invoke_tool service",
    priority: 1,
    estimate: 5,
    labels: ["tier-1", "platform", "backend"],
    description: `Single audited entry point for all agent and workflow tool calls.

## Problem
Slack/email/webhook work via step executor only. CRM actions are registry metadata (\`goal_service.py:13-21\`).

## Acceptance criteria
- [ ] \`invoke_tool(ctx, action, params) -> NormalizedResult\`
- [ ] Audit log: org_id, agent_id, task_id, run_id, connector_id, action
- [ ] Rate limiting (extend \`rate_limit.py\`)
- [ ] Retries with backoff for transient vendor errors
- [ ] Vendor errors → AuthExpired | RateLimited | ValidationError
- [ ] Normalized outputs: Contact, Deal, Ticket

## Key files
\`backend/app/connectors/\`, \`backend/app/workflows/handlers.py\`

**Blocks:** T1-006, T1-012, T1-013`,
  },
  {
    id: "T1-002",
    epic: "epic-a",
    title: "Agent-tool permission model",
    priority: 1,
    estimate: 3,
    labels: ["tier-1", "platform", "security"],
    description: `Scope-based tool permissions per agent (read vs write).

## Acceptance criteria
- [ ] Migration: \`agent_tool_permissions(org_id, agent_id, connector_id, scopes[], granted_by, granted_at, expires_at)\`
- [ ] \`invoke_tool\` denies when scope missing (e.g. \`hubspot:deals:write\`)
- [ ] Admin API to grant/revoke scopes
- [ ] Demo seed agents get appropriate HubSpot scopes

## Key files
\`backend/app/operators/repository.py:336-343\`, \`backend/app/policy/engine.py\`

**Depends on:** T1-001 | **Blocks:** T1-006`,
  },
  {
    id: "T1-003",
    epic: "epic-a",
    title: "Merge dual execution engines",
    priority: 1,
    estimate: 5,
    labels: ["tier-1", "workflows", "backend"],
    description: `Webhook triggers use stub ExecutionService; /execute uses real handlers.

## Acceptance criteria
- [ ] Webhook path (\`webhooks/workflow_triggers.py\`) uses same executor as manual /execute
- [ ] Stub action nodes removed or bridged to invoke_tool
- [ ] Integration test: webhook trigger → Slack post succeeds

## Key files
\`execution_service.py:149-151\`, \`workflows/execute.py\`, \`webhooks/workflow_triggers.py\`

**Depends on:** T1-001 | **Blocks:** T1-007, T1-010`,
  },
  {
    id: "T1-004",
    epic: "epic-a",
    title: "Real connector OAuth UX",
    priority: 2,
    estimate: 3,
    labels: ["tier-1", "frontend", "connectors"],
    description: `Replace simulated OAuth in connectors UI.

## Acceptance criteria
- [ ] Replace mock handleOAuthConnect (\`connectors/page.tsx:762-771\`)
- [ ] Backend OAuth start/callback; tokens in connector_secrets (encrypted)
- [ ] Connection status reflects real token validity
- [ ] HubSpot first supported OAuth provider

**Depends on:** T1-001 | **Blocks:** T1-005`,
  },
  {
    id: "T1-004a",
    epic: "epic-b",
    title: "Platform setup: HubSpot OAuth app & deployment secrets",
    priority: 1,
    estimate: 1,
    labels: ["tier-1", "hubspot", "ops", "platform"],
    description: `**Operator checklist (one-time per env)** — not a customer task.

- [ ] One HubSpot developer app (prod / optional sandbox)
- [ ] Redirect URI: \`{API_PUBLIC_URL}/api/connectors/oauth/hubspot/callback\`
- [ ] Env: \`HUBSPOT_CLIENT_ID\`, \`HUBSPOT_CLIENT_SECRET\`, \`CONNECTOR_SECRETS_ENCRYPTION_KEY\`, \`NEXT_PUBLIC_APP_URL\`, \`API_PUBLIC_URL\`
- [ ] Smoke: Connectors UI → Connect HubSpot → test connection

See \`scripts/create-hubspot-platform-setup-linear-issue.mjs\` and \`backend/.env.example\`.

**Depends on:** T1-004 (STA-13 code) | **Blocks:** T1-005`,
  },
  {
    id: "T1-005",
    epic: "epic-b",
    title: "HubSpot OAuth + token lifecycle",
    priority: 1,
    estimate: 3,
    labels: ["tier-1", "hubspot", "integration"],
    description: `HubSpot in registry only; demo agents declare systems: ["hubspot"] but no API client.

## Acceptance criteria
- [ ] HubSpot OAuth2 (sandbox + prod)
- [ ] Token refresh before expiry
- [ ] Encrypted storage (Fernet/crypto pattern)
- [ ] Admin connects HubSpot from connectors UI

**Depends on:** T1-004, T1-004a (platform HubSpot app + deployment secrets) | **Blocks:** T1-006, T1-007`,
  },
  {
    id: "T1-006",
    epic: "epic-b",
    title: "HubSpot v1 actions (5 core)",
    priority: 1,
    estimate: 5,
    labels: ["tier-1", "hubspot", "sales-agent"],
    description: `V1 actions:
1. hubspot.contacts.get
2. hubspot.contacts.update
3. hubspot.notes.create
4. hubspot.deals.update_stage
5. hubspot.sequences.enroll

## Demo
Task "Update deal stage for Acme to Qualified" → deal updated in HubSpot sandbox.

**Agent impact:** Sales ~8% → ~40%

**Depends on:** T1-001, T1-002, T1-005`,
  },
  {
    id: "T1-007",
    epic: "epic-b",
    title: "HubSpot inbound triggers → workflows",
    priority: 2,
    estimate: 5,
    labels: ["tier-1", "hubspot", "workflows"],
    description: `V1 triggers: contact.creation, deal.propertyChange

## Acceptance criteria
- [ ] HubSpot webhook subscription on connector connect
- [ ] Inbound events start workflow runs via merged executor
- [ ] Payload normalized to Contact/Deal in run context
- [ ] Demo: form submit → qualification workflow runs

**Reference:** \`org_seed_service.py:89-100\`

**Depends on:** T1-003, T1-005, T1-006`,
  },
  {
    id: "T1-008",
    epic: "epic-c",
    title: "Cross-agent handoff data bus",
    priority: 2,
    estimate: 5,
    labels: ["tier-1", "agents", "platform"],
    description: `next_agent_id validated but never routed (\`workflows/schema.py:116-120\`).

## Acceptance criteria
- [ ] agent_handoffs table with briefing JSONB
- [ ] Briefing schema: { contact, deal, decision, artifacts[] }
- [ ] Receiving agent task payload includes briefing
- [ ] Audit trail shows handoff events

**Depends on:** T1-001 | **Blocks:** T1-009`,
  },
  {
    id: "T1-009",
    epic: "epic-c",
    title: "Wire next_agent_id runtime routing",
    priority: 2,
    estimate: 3,
    labels: ["tier-1", "agents", "workflows"],
    description: `Sales → Marketing handoff without human coordinator.

## Demo
Sales qualifies lead → Marketing Agent auto-receives enroll task.

**Depends on:** T1-008, T1-006`,
  },
  {
    id: "T1-010",
    epic: "epic-c",
    title: "Workflow builder persistence (save + run)",
    priority: 2,
    estimate: 3,
    labels: ["tier-1", "frontend", "workflows"],
    description: `Builder save is simulated (\`builder/page.tsx:2974-2979\`).

## Acceptance criteria
- [ ] Save persists graph to backend
- [ ] Run triggers real /execute path
- [ ] Seed workflow editable and runnable end-to-end

**Depends on:** T1-003`,
  },
  {
    id: "T1-011",
    epic: "epic-d",
    title: "Department-scoped RAG",
    priority: 3,
    estimate: 3,
    labels: ["tier-1", "rag", "platform"],
    description: `RAG is org-wide; agents.department ignored in retrieval.

## Acceptance criteria
- [ ] department_id (+ optional agent_id) on rag_sources
- [ ] RAGService filters by agent department
- [ ] Sales playbook → only Sales Agent retrieves

**Key files:** \`backend/app/rag/\`, rag migrations`,
  },
  {
    id: "T1-012",
    epic: "epic-d",
    title: "Zendesk v1 (CS Agent)",
    priority: 3,
    estimate: 5,
    labels: ["tier-1", "zendesk", "cs-agent"],
    description: `V1: read/create/update ticket, add tag, escalate. Stretch: ticket.created trigger.

**Depends on:** T1-001, T1-002`,
  },
  {
    id: "T1-013",
    epic: "epic-d",
    title: "GitHub v1 (DevOps Agent)",
    priority: 3,
    estimate: 3,
    labels: ["tier-1", "github", "devops-agent"],
    description: `V1: list PRs, assign reviewer, create issue, comment. Trigger: pull_request.opened.

**Depends on:** T1-001, T1-002`,
  },
  {
    id: "T1-014",
    epic: "epic-d",
    title: "Calendar integration (Google / M365) — stretch",
    priority: 4,
    estimate: 5,
    labels: ["tier-1-stretch", "calendar", "sales-agent"],
    description: `V1: check availability, create event, send invite. Defer if HubSpot path slips.

**Depends on:** T1-004`,
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
        `${LINEAR} label create -n ${shQuote(name)} -t ${shQuote(team)} -c "#5E6AD2"`,
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
  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "linear-tier1-"));
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

1. Create a key at https://linear.app/settings/account/security
2. Run:

   $env:LINEAR_API_KEY="lin_api_..."
   node scripts/create-tier1-linear-issues.mjs

Or authenticate once:

   npx @schpet/linear-cli auth login -k lin_api_... --workspace staqbot --plaintext
`);
    process.exit(1);
  }

  console.log("🔐 Using LINEAR_API_KEY from environment...");
  process.env.LINEAR_API_KEY = API_KEY;

  let team = process.env.LINEAR_TEAM;
  if (!team) {
    console.log("🔍 Detecting team...");
    const teamsOut = run(`${LINEAR} team list`, { capture: true });
    const teamMatch = teamsOut.match(/\b(STA|[A-Z]{2,6})\b/);
    team = teamMatch?.[1] ?? "STA";
    console.log(`   Using team: ${team}`);
  }

  const targetDate = new Date();
  targetDate.setDate(targetDate.getDate() + 30);
  const targetDateStr = targetDate.toISOString().slice(0, 10);

  console.log("📋 Creating initiative...");
  try {
    run(
      `${LINEAR} initiative create -n ${shQuote("Tier 1 — Integration Platform (30 days)")} -s active --target-date ${targetDateStr} -d ${shQuote("Turn demo seed workflow (Sales qualifies → Marketing enrolls) into executable reality. Audit: May 29, 2026.")}`,
      { capture: true },
    );
  } catch (e) {
    console.warn("   ⚠ Initiative may already exist or need manual creation:", e.message.split("\n")[0]);
  }

  const projectName = "Tier 1 Integration Platform";
  console.log("📁 Creating project...");
  try {
    run(
      `${LINEAR} project create -n ${shQuote(projectName)} -t ${shQuote(team)} -s started --target-date ${targetDateStr} --initiative ${shQuote("Tier 1 — Integration Platform (30 days)")} -d ${shQuote("HubSpot + unified tool execution + cross-agent handoffs. 30-day Tier 1 scope.")}`,
      { capture: true },
    );
  } catch (e) {
    console.warn("   ⚠ Project may already exist:", e.message.split("\n")[0]);
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

  console.log("\n✅ Done! Created 4 epics + 14 issues.\n");
  console.log("| Ref | Linear | Title | Epic |");
  console.log("|-----|--------|-------|------|");
  for (const row of created) {
    console.log(`| ${row.ref} | ${row.linear} | ${row.title} | ${row.parent} |`);
  }
  console.log(`\n🔗 https://linear.app/${WORKSPACE}`);
}

main();
