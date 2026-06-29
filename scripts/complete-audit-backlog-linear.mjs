#!/usr/bin/env node
/**
 * Mark Phase 3/4 audit backlog issues Done after deliverables land in repo.
 *
 * Usage:
 *   node scripts/complete-audit-backlog-linear.mjs
 *   node scripts/complete-audit-backlog-linear.mjs --dry-run
 */

import { spawnSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const DRY_RUN = process.argv.includes("--dry-run");
const WORKSPACE = process.env.LINEAR_WORKSPACE || "staqbot";

const ISSUES = [
  {
    id: "STA-272",
    links: [
      {
        url: "https://github.com/staqbot/gravitre-saas-backend/blob/main/docs/platform-reconciliation/CANONICAL_SCHEMA_DECISION.md",
        title: "CANONICAL_SCHEMA_DECISION.md",
      },
    ],
  },
  {
    id: "STA-280",
    links: [
      {
        url: "https://github.com/staqbot/gravitre-saas-backend/blob/main/docs/integration/HRIS_REFERENCE_PATTERN.md",
        title: "HRIS_REFERENCE_PATTERN.md",
      },
    ],
  },
  {
    id: "STA-282",
    links: [
      {
        url: "https://github.com/staqbot/gravitre-saas-backend/blob/main/scripts/check-tier4-connector-audit.py",
        title: "check-tier4-connector-audit.py",
      },
    ],
  },
  {
    id: "STA-284",
    links: [
      {
        url: "https://github.com/staqbot/gravitre-saas-backend/blob/main/docs/ai/EXECUTION_ENGINE_DESIGN.md",
        title: "EXECUTION_ENGINE_DESIGN.md",
      },
    ],
  },
  {
    id: "STA-285",
    links: [
      {
        url: "https://github.com/staqbot/gravitre-saas-backend/blob/main/backend/app/connectors/simulation_coverage.py",
        title: "simulation_coverage.py",
      },
    ],
  },
  {
    id: "STA-287",
    links: [
      {
        url: "https://github.com/staqbot/gravitre-saas-backend/blob/main/docs/ai/PARTIAL_FAILURE_POLICY.md",
        title: "PARTIAL_FAILURE_POLICY.md",
      },
    ],
  },
  {
    id: "STA-289",
    links: [
      {
        url: "https://github.com/staqbot/gravitre-saas-backend/blob/main/docs/ai/GROUND_TRUTH_OUTCOME_ROADMAP.md",
        title: "GROUND_TRUTH_OUTCOME_ROADMAP.md",
      },
    ],
  },
];

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

function getApiKey() {
  const fromEnv = process.env.LINEAR_API_KEY || process.env.LINEAR_TOKEN;
  if (fromEnv) return fromEnv.trim();
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

async function getDoneStateId(apiKey, identifier) {
  const data = await gql(
    apiKey,
    `query($id: String!) {
      issue(id: $id) {
        team { states { nodes { id name type } } }
      }
    }`,
    { id: identifier },
  );
  const states = data.issue?.team?.states?.nodes || [];
  const done = states.find((s) => s.type === "completed" || s.name.toLowerCase() === "done");
  if (!done) throw new Error(`No Done state for ${identifier}`);
  return done.id;
}

async function completeIssue(apiKey, issue) {
  const stateId = await getDoneStateId(apiKey, issue.id);
  if (DRY_RUN) {
    console.log(`Would complete ${issue.id} → state ${stateId}`);
    return;
  }
  await gql(
    apiKey,
    `mutation($id: String!, $input: IssueUpdateInput!) {
      issueUpdate(id: $id, input: $input) { success issue { identifier state { name } } }
    }`,
    {
      id: issue.id,
      input: {
        stateId,
      },
    },
  );
  console.log(`Completed ${issue.id}`);
}

async function main() {
  const apiKey = getApiKey();
  if (!apiKey) {
    console.error("No Linear auth. Set LINEAR_API_KEY or run: linear auth login");
    process.exit(1);
  }
  for (const issue of ISSUES) {
    await completeIssue(apiKey, issue);
  }
  console.log(DRY_RUN ? "Dry run done." : `Marked ${ISSUES.length} issues Done.`);
}

main().catch((err) => {
  console.error(err.message || err);
  process.exit(1);
});
