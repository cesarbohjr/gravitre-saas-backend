#!/usr/bin/env node
/**
 * Create AI Intelligence Upgrade issues in Linear (Phase 3 backend B1–B8 + v0 F1–F4).
 *
 * Usage:
 *   $env:LINEAR_API_KEY="lin_api_..."
 *   npm run linear:ai-intelligence
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

const T1 = { handoff: "STA-17", rag: "STA-20", builder: "STA-19" };
const T5 = {
  digitalTwin: "STA-120",
  failurePredict: "STA-122",
  autoSuggest: "STA-123",
  handoffB2B: "STA-116",
};

const DELIVERABLE = "docs/delivery/GRAVITRE_AI_INTELLIGENCE_UPGRADE.md";
const V0_PROMPTS = "docs/design/V0_AI_INTELLIGENCE_PROMPTS.md";

const EPICS = [
  {
    key: "epic-a",
    title: "[Epic A] Agent Intelligence Layer (AI Upgrade)",
    description: `Make every agent a genuine LLM specialist: RAG + ReAct + tools + role personas.

**Closes gap:** \`agent_jobs.py\` single-shot plan-only completion (score 4/10)

**Child issues:** AI-001 through AI-004

**Requires:** ${T1.rag}, ${T1.handoff}, STA-10 invoke_tool

**Spec:** ${DELIVERABLE} Section 2`,
    labels: ["ai-intelligence", "agents", "platform"],
    estimate: 21,
  },
  {
    key: "epic-b",
    title: "[Epic B] Workflow Execution Engine (AI Upgrade)",
    description: `Graph-native execution: topological order, parallel batches, approval gates, per-node logs.

**Closes gap:** Runtime trusts compiled step list; no parallel \`asyncio.gather\` batches

**Child issues:** AI-005 through AI-008

**Builds on:** ${T1.builder}, STA-12 execute.py, ${T5.digitalTwin}

**Spec:** ${DELIVERABLE} Section 3`,
    labels: ["ai-intelligence", "workflows", "platform"],
    estimate: 21,
  },
  {
    key: "epic-c",
    title: "[Epic C] Meson AI Copilot (AI Upgrade)",
    description: `Meson watches, learns, and suggests — workflow builder copilot + anomalies + optimizations.

**Closes gap:** Meson wizard UI only; no \`meson_service.py\` or \`/api/meson/*\`

**Child issues:** AI-009 through AI-012

**Related (Tier 5):** ${T5.failurePredict}, ${T5.autoSuggest} — Meson unifies these under one product layer

**Spec:** ${DELIVERABLE} Section 4`,
    labels: ["ai-intelligence", "meson", "platform"],
    estimate: 16,
  },
  {
    key: "epic-d",
    title: "[Epic D] Assistant & Org Context (AI Upgrade)",
    description: `Persistent memory, org context injection, expanded tools, true token streaming.

**Closes gap:** Pseudo-stream (\`_TEXT_DELTA_CHARS=24\`); chat not wired to conversations table

**Child issues:** AI-013 through AI-017

**Requires:** conversations migration (exists), STA-90 model policy

**Spec:** ${DELIVERABLE} Section 5`,
    labels: ["ai-intelligence", "assistant", "platform"],
    estimate: 21,
  },
  {
    key: "epic-e",
    title: "[Epic E] Enhanced RAG (AI Upgrade)",
    description: `Production RAG: BM25 + vector RRF + cross-encoder reranking.

**Closes gap:** Lexical overlap rerank only in \`rag_service.py\`

**Child issues:** AI-018

**Requires:** ${T1.rag}

**Spec:** ${DELIVERABLE} — B5`,
    labels: ["ai-intelligence", "rag", "ai"],
    estimate: 8,
  },
  {
    key: "epic-f",
    title: "[Epic F] v0 Intelligence UI (AI Upgrade)",
    description: `Frontend prompts F1–F4 — implement in v0 branch, merge preserving backend.

**Child issues:** AI-019 through AI-022

**Prompts:** ${V0_PROMPTS}

**Do not implement in Cursor** — v0.dev only`,
    labels: ["ai-intelligence", "frontend", "v0"],
    estimate: 13,
  },
  {
    key: "epic-g",
    title: "[Epic G] Discovery & Verification (AI Upgrade)",
    description: `Phase 1–2 audit deliverable + Phase 5 test/smoke verification.

**Child issues:** AI-023, AI-024`,
    labels: ["ai-intelligence", "docs", "qa"],
    estimate: 5,
  },
];

const ISSUES = [
  {
    id: "AI-001",
    epic: "epic-a",
    title: "Universal AgentIntelligence layer",
    priority: 2,
    estimate: 8,
    labels: ["ai-intelligence", "agents", "platform"],
    description: `## Goal
Create \`backend/app/operators/agent_intelligence.py\` — universal stack for every agent task.

## Acceptance criteria
- [ ] \`AgentIntelligence.execute_task()\` loads RAG, org context, task history, handoff briefing
- [ ] Builds full system prompt (identity, knowledge, org state, tools, rules)
- [ ] Selects model by task complexity via model_router
- [ ] Returns structured \`AgentResult\` for handoffs
- [ ] All agent job paths call this layer (not ad hoc complete())

## Key files
\`agent_jobs.py\`, \`handoff_service.py\`, \`model_router.py\`

## Depends on
${T1.rag}, ${T1.handoff}`,
  },
  {
    id: "AI-002",
    epic: "epic-a",
    title: "Role-specific agent system prompts",
    priority: 2,
    estimate: 5,
    labels: ["ai-intelligence", "agents", "platform"],
    description: `## Goal
Create \`backend/app/operators/agent_prompts.py\` with expert personas.

## Prompts required
- SALES, MARKETING, FINANCE, HR, CS, DEVOPS, DEFAULT

## Each prompt includes
Expert persona, expertise areas, judgment heuristics, constraints, handoff output format

## Acceptance criteria
- [ ] AgentIntelligence selects prompt by agent role/department
- [ ] Custom agents fall back to DEFAULT with agent-specific overrides`,
  },
  {
    id: "AI-003",
    epic: "epic-a",
    title: "ReAct reasoning engine for agents",
    priority: 2,
    estimate: 8,
    labels: ["ai-intelligence", "agents", "ai"],
    description: `## Goal
Create \`backend/app/operators/react_engine.py\` — Reason + Act + Observe loop.

## Acceptance criteria
- [ ] Max iterations (default 10) with transparent reasoning trace
- [ ] Tool call execution via invoke_tool / agent permissions
- [ ] \`needs_human_input\` when stuck (not guessing)
- [ ] \`max_iterations_reached\` recommends workflow breakdown
- [ ] Audit log of thought/act/observe per iteration

## Depends on
AI-001, STA-10, STA-11`,
  },
  {
    id: "AI-004",
    epic: "epic-a",
    title: "Wire RAG retrieval into every agent task",
    priority: 2,
    estimate: 5,
    labels: ["ai-intelligence", "agents", "rag"],
    description: `## Goal
Before every agent response, retrieve top-k chunks scoped to agent_id + org.

## Acceptance criteria
- [ ] \`RAGService.query(..., agent_id=)\` called in AgentIntelligence
- [ ] Sources cited in agent output
- [ ] Empty KB handled gracefully (ask user to add knowledge)

## Depends on
${T1.rag}, AI-001`,
  },
  {
    id: "AI-005",
    epic: "epic-b",
    title: "WorkflowExecutionEngine — graph-native runtime",
    priority: 2,
    estimate: 8,
    labels: ["ai-intelligence", "workflows", "platform"],
    description: `## Goal
Create \`backend/app/workflows/execution_engine.py\` — execute from connections, not just compiled steps.

## Acceptance criteria
- [ ] Build execution graph from nodes + edges
- [ ] Validate graph (cycles, reachability)
- [ ] Topological batch execution — B cannot start until A completes
- [ ] Each node receives full upstream output as input context
- [ ] Integrate with existing run logging

## Builds on
\`execute.py\`, \`builder_sync.py\``,
  },
  {
    id: "AI-006",
    epic: "epic-b",
    title: "Parallel branch execution and merge",
    priority: 2,
    estimate: 5,
    labels: ["ai-intelligence", "workflows", "platform"],
    description: `## Goal
Nodes in the same topological batch run concurrently via \`asyncio.gather\`.

## Acceptance criteria
- [ ] Parallel fan-out executes simultaneously
- [ ] Merge node receives combined outputs before continuing
- [ ] Failure in one parallel branch respects per-node on_failure policy

## Depends on
AI-005`,
  },
  {
    id: "AI-007",
    epic: "epic-b",
    title: "Human approval pause/resume in workflow engine",
    priority: 2,
    estimate: 5,
    labels: ["ai-intelligence", "workflows", "platform"],
    description: `## Goal
Approval nodes pause workflow; resume via API when human approves/rejects.

## Acceptance criteria
- [ ] Run status \`awaiting_approval\` with paused_at_node
- [ ] Approval context stored for UI (F3)
- [ ] Resume continues from next node with approval outcome in context
- [ ] Reject path configurable (fail workflow / alternate branch)

## Depends on
AI-005, STA-108 interrupt patterns`,
  },
  {
    id: "AI-008",
    epic: "epic-b",
    title: "Per-node retry/skip/fail + granular execution logs",
    priority: 3,
    estimate: 5,
    labels: ["ai-intelligence", "workflows", "platform"],
    description: `## Goal
Each node: on_failure = retry | skip | fail_workflow. Full I/O + tokens logged per node.

## Acceptance criteria
- [ ] Retry with backoff configurable per node
- [ ] Skip marks node in context.skipped_nodes
- [ ] Log: start/end/duration, input, output, model, tokens, errors
- [ ] Debuggable from run monitor UI (F3)

## Depends on
AI-005`,
  },
  {
    id: "AI-009",
    epic: "epic-c",
    title: "MesonService core — suggestions, anomalies, optimizations",
    priority: 2,
    estimate: 8,
    labels: ["ai-intelligence", "meson", "platform"],
    description: `## Goal
Create \`backend/app/services/meson_service.py\`.

## Methods
- \`get_workflow_suggestions()\` — next node recommendations
- \`detect_anomalies()\` — error rate / latency / auth failures
- \`generate_optimization()\` — bottleneck analysis per workflow
- \`get_proactive_insights()\` — org-wide insights

## Acceptance criteria
- [ ] LLM + pattern analysis (similar workflows in org)
- [ ] Confidence scores on suggestions
- [ ] Plain-English explanations for alerts`,
  },
  {
    id: "AI-010",
    epic: "epic-c",
    title: "Meson API router (/api/meson/*)",
    priority: 2,
    estimate: 5,
    labels: ["ai-intelligence", "meson", "platform"],
    description: `## Goal
Create \`backend/app/routers/meson.py\` and register in main.

## Endpoints
- POST /api/meson/suggestions
- GET /api/meson/alerts
- GET /api/meson/optimizations/{workflow_id}
- GET /api/meson/insights
- POST /api/meson/apply/{suggestion_id}
- POST /api/meson/feedback
- GET /api/meson/preferences

## Depends on
AI-009`,
  },
  {
    id: "AI-011",
    epic: "epic-c",
    title: "Meson user preference learning",
    priority: 3,
    estimate: 5,
    labels: ["ai-intelligence", "meson", "platform"],
    description: `## Goal
\`learn_user_preferences()\` — model choices, workflow patterns, working hours.

## Acceptance criteria
- [ ] Preferences stored per user+org
- [ ] Injected into Meson suggestion prompts
- [ ] GET /api/meson/preferences returns learned defaults`,
  },
  {
    id: "AI-012",
    epic: "epic-c",
    title: "Meson feedback loop (accept/dismiss suggestions)",
    priority: 3,
    estimate: 3,
    labels: ["ai-intelligence", "meson", "platform"],
    description: `## Goal
POST /api/meson/feedback improves suggestion quality over time.

## Acceptance criteria
- [ ] Track accepted vs dismissed with reason
- [ ] Dismissed suggestions not resurfaced for same workflow state
- [ ] Metrics for suggestion acceptance rate`,
  },
  {
    id: "AI-013",
    epic: "epic-d",
    title: "Wire assistant chat to persistent conversations",
    priority: 2,
    estimate: 8,
    labels: ["ai-intelligence", "assistant", "platform"],
    description: `## Goal
\`/api/assistant/chat\` accepts \`conversation_id\`, persists messages, returns id.

## Acceptance criteria
- [ ] Create conversation on first message
- [ ] Load last 20 messages from DB as history
- [ ] Persist user + assistant messages with tokens/model metadata
- [ ] Background: generate title on first message
- [ ] Frontend sidebar (F4) can list via existing /api/conversations

## Key files
\`routers/assistant.py\`, \`routers/conversations.py\``,
  },
  {
    id: "AI-014",
    epic: "epic-d",
    title: "Conversation context summarization (>80% window)",
    priority: 3,
    estimate: 5,
    labels: ["ai-intelligence", "assistant", "ai"],
    description: `## Goal
When history exceeds 80% context window, summarize oldest half.

## Acceptance criteria
- [ ] Store \`last_summary\` on conversations row
- [ ] Drop summarized messages from active context
- [ ] Summary injected into system prompt block

## Depends on
AI-013`,
  },
  {
    id: "AI-015",
    epic: "epic-d",
    title: "OrgContextService — live org state for AI prompts",
    priority: 2,
    estimate: 5,
    labels: ["ai-intelligence", "assistant", "platform"],
    description: `## Goal
Create \`backend/app/services/org_context_service.py\`.

## Injects into every assistant + agent call
Agents, workflows, integrations, recent runs, active alerts

## Acceptance criteria
- [ ] 60s in-memory cache per org
- [ ] \`build_context(org_id, user_id, depth)\` returns formatted markdown
- [ ] Used by assistant system prompt and AgentIntelligence`,
  },
  {
    id: "AI-016",
    epic: "epic-d",
    title: "Expanded assistant tool suite",
    priority: 2,
    estimate: 8,
    labels: ["ai-intelligence", "assistant", "platform"],
    description: `## Goal
Add tools: run_agent_task, get_workflow_runs, get_analytics, search_web (Tavily), generate_document, create_workflow.

## Acceptance criteria
- [ ] Each tool org-scoped with fence_untrusted on results
- [ ] Tool activity visible in assistant UI (F4)
- [ ] Existing 3 tools unchanged

## Depends on
STA-10, AI-015`,
  },
  {
    id: "AI-017",
    epic: "epic-d",
    title: "True token streaming (model_router.stream + assistant SSE)",
    priority: 2,
    estimate: 8,
    labels: ["ai-intelligence", "assistant", "ai"],
    description: `## Goal
Replace pseudo-stream with provider-native token streaming.

## Acceptance criteria
- [ ] \`model_router.stream()\` AsyncGenerator with guardrails pre-flight
- [ ] OpenAI + Anthropic adapters implement stream()
- [ ] Assistant yields SSE tokens as generated (not 24-char chunks)
- [ ] Usage logged from final streaming chunk
- [ ] curl --no-buffer shows incremental tokens

## Key files
\`model_router.py\`, \`providers/*\`, \`routers/assistant.py\``,
  },
  {
    id: "AI-018",
    epic: "epic-e",
    title: "Cross-encoder reranking + BM25 hybrid RAG",
    priority: 3,
    estimate: 8,
    labels: ["ai-intelligence", "rag", "ai"],
    description: `## Goal
Enhance \`rag_service.py\`: vector top-20 + BM25 top-20 → RRF → cross-encoder rerank → top-5.

## Acceptance criteria
- [ ] sentence-transformers CrossEncoder (ms-marco-MiniLM-L-6-v2)
- [ ] rank-bm25 for keyword search
- [ ] Filter below rerank threshold 0.3
- [ ] Lazy-load reranker (optional env flag to disable)
- [ ] Tests with mocked encoder

## Depends on
${T1.rag}`,
  },
  {
    id: "AI-019",
    epic: "epic-f",
    title: "v0 F1 — Meson copilot panel (workflow builder)",
    priority: 2,
    estimate: 5,
    labels: ["ai-intelligence", "frontend", "v0", "meson"],
    description: `## Goal
Implement v0 prompt F1 — right-side Meson panel on workflow builder.

## Acceptance criteria
- [ ] 280px collapsible panel; "✨ Meson" toolbar toggle
- [ ] Sections: suggestions, alerts, optimizations
- [ ] Wire to /api/meson/* when live; mock until AI-010 ships
- [ ] Dismissed suggestions in localStorage per workflowId

## Prompt
${V0_PROMPTS} — section F1

## Depends on
AI-010 (backend); mock OK for v0 first pass`,
  },
  {
    id: "AI-020",
    epic: "epic-f",
    title: "v0 F2 — Intelligent agent cards",
    priority: 3,
    estimate: 5,
    labels: ["ai-intelligence", "frontend", "v0", "agents"],
    description: `## Goal
Implement v0 prompt F2 — success rate, tasks, knowledge pill, last activity, model badge.

## Prompt
${V0_PROMPTS} — section F2

## Depends on
AI-001 (live metrics); mock stats OK initially`,
  },
  {
    id: "AI-021",
    epic: "epic-f",
    title: "v0 F3 — Workflow execution timeline",
    priority: 2,
    estimate: 5,
    labels: ["ai-intelligence", "frontend", "v0", "workflows"],
    description: `## Goal
Implement v0 prompt F3 — CI/CD-style run monitor with approval gates.

## Prompt
${V0_PROMPTS} — section F3

## Depends on
AI-008 (granular logs), AI-007 (approval UI)`,
  },
  {
    id: "AI-022",
    epic: "epic-f",
    title: "v0 F4 — Assistant intelligence upgrade",
    priority: 2,
    estimate: 8,
    labels: ["ai-intelligence", "frontend", "v0", "assistant"],
    description: `## Goal
Implement v0 prompt F4 — conversation sidebar, mode selector, org context pill, follow-ups, tool activity.

## Prompt
${V0_PROMPTS} — section F4

## Depends on
AI-013, AI-015, AI-017`,
  },
  {
    id: "AI-023",
    epic: "epic-g",
    title: "Phase 1–2 discovery deliverable (audit + gap analysis)",
    priority: 4,
    estimate: 3,
    labels: ["ai-intelligence", "docs"],
    description: `## Goal
Principal-engineer audit documented with scores and gap table.

## Deliverable
${DELIVERABLE}

## Acceptance criteria
- [x] Architecture map
- [x] Gap analysis per dimension
- [x] Before scores (4.5/10 overall)
- [x] Implementation roadmap B1–B8
- [x] v0 prompts F1–F4 in ${V0_PROMPTS}`,
  },
  {
    id: "AI-024",
    epic: "epic-g",
    title: "Phase 5 verification — pytest + live smoke",
    priority: 3,
    estimate: 5,
    labels: ["ai-intelligence", "qa"],
    description: `## Goal
Verify all AI upgrade work with automated + live tests.

## Acceptance criteria
- [ ] pytest: new tests for AgentIntelligence, ReAct, WorkflowExecutionEngine, Meson, streaming
- [ ] \`npm run smoke:ai-intelligence\` script (assistant stream, meson suggestions, agent task)
- [ ] Target scores documented in deliverable Section 8 (overall 8/10)
- [ ] Production smoke on gravitre.app after deploy

## Depends on
AI-001 through AI-022`,
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

function createIssue({ title, description, team, parent, project, priority, estimate, labels, state }) {
  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "linear-ai-"));
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
  if (parent) parts.push(`--parent ${shQuery(parent)}`);
  if (project) parts.push(`--project ${shQuote(project)}`);
  if (priority) parts.push(`-p ${priority}`);
  if (estimate) parts.push(`--estimate ${estimate}`);
  if (state) parts.push(`--state ${shQuote(state)}`);
  for (const label of labels ?? []) {
    parts.push(`-l ${shQuote(label)}`);
  }

  const output = run(parts.join(" "), { capture: true });
  fs.rmSync(tmpDir, { recursive: true, force: true });

  const id = parseIssueId(output);
  if (!id) throw new Error(`Could not parse issue id from output:\n${output}`);
  return id;
}

function shQuery(value) {
  return shQuote(value);
}

function main() {
  if (!API_KEY) {
    console.error(`\n❌ LINEAR_API_KEY is not set.\n   npm run linear:ai-intelligence\n`);
    process.exit(1);
  }

  console.log("🔐 Using LINEAR_API_KEY from environment...");
  process.env.LINEAR_API_KEY = API_KEY;

  const team = process.env.LINEAR_TEAM || "Staqbot";
  const targetDate = new Date();
  targetDate.setDate(targetDate.getDate() + 180);
  const targetDateStr = targetDate.toISOString().slice(0, 10);

  const initiativeName = "AI Intelligence Upgrade — Gravitre Operating Model";
  const projectName = "AI Intelligence Platform";

  console.log("📋 Creating initiative...");
  try {
    run(
      `${LINEAR} initiative create -n ${shQuote(initiativeName)} -s planned --target-date ${targetDateStr} -d ${shQuote("Unified intelligence layer: ReAct agents, Meson copilot, graph workflows, assistant memory + streaming. Requires Tier 1–5 platform.")}`,
      { capture: true },
    );
  } catch (e) {
    console.warn("   ⚠ Initiative:", e.message.split("\n")[0]);
  }

  console.log("📁 Creating project...");
  try {
    run(
      `${LINEAR} project create -n ${shQuote(projectName)} -t ${shQuote(team)} -s planned --target-date ${targetDateStr} --initiative ${shQuote(initiativeName)} -d ${shQuote("Phase 3 backend B1–B8 + v0 frontend F1–F4. Target overall score 8/10.")}`,
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
      state: issue.id === "AI-023" ? "Done" : undefined,
    });
    created.push({ ref: issue.id, linear: id, title: issue.title, parent });
    console.log(`   ✓ ${id}  [${issue.id}] ${issue.title}`);
  }

  const outPath = path.join(__dirname, "..", "docs", "ai", "ai-intelligence-linear-ids.json");
  fs.mkdirSync(path.dirname(outPath), { recursive: true });
  fs.writeFileSync(
    outPath,
    JSON.stringify({ createdAt: new Date().toISOString(), epics: epicIds, issues: created }, null, 2),
  );

  console.log("\n✅ Done! Created 7 epics + 24 issues.\n");
  console.log("| Ref | Linear | Title | Epic |");
  console.log("|-----|--------|-------|------|");
  for (const row of created) {
    console.log(`| ${row.ref} | ${row.linear} | ${row.title} | ${row.parent} |`);
  }
  console.log(`\n📄 IDs saved to docs/ai/ai-intelligence-linear-ids.json`);
  console.log(`🔗 https://linear.app/${WORKSPACE}`);
}

main();
