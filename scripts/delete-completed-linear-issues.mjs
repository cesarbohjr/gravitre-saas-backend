#!/usr/bin/env node
/**
 * Delete all completed Linear issues in a team to free workspace quota.
 *
 * Auth (first match wins):
 *   LINEAR_API_KEY or LINEAR_TOKEN env
 *   @schpet/linear-cli keyring (`linear auth login`)
 *
 * Usage:
 *   node scripts/delete-completed-linear-issues.mjs
 *   node scripts/delete-completed-linear-issues.mjs --dry-run
 */

import { spawnSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const DRY_RUN = process.argv.includes("--dry-run");
const WORKSPACE = process.env.LINEAR_WORKSPACE || "staqbot";
const TEAM_KEY = process.env.LINEAR_TEAM || "STA";

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

  const prefix = linearCmd.includes("npx") ? "" : path.dirname(linearCmd);
  const args = linearCmd.includes("npx")
    ? ["--yes", "--prefix", path.join(process.env.LOCALAPPDATA || "", "linear-cli-tool"), "@schpet/linear-cli", "auth", "token", "--workspace", WORKSPACE]
    : ["auth", "token", "--workspace", WORKSPACE];

  const cmd = linearCmd.includes("npx") ? "npx" : linearCmd;
  const result = spawnSync(cmd, linearCmd.includes("npx") ? args : args, {
    encoding: "utf8",
    shell: true,
    cwd: prefix || undefined,
  });
  if (result.status !== 0) return null;
  const token = (result.stdout || "").trim();
  return token || null;
}

async function gql(apiKey, query, variables = {}) {
  const res = await fetch("https://api.linear.app/graphql", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: apiKey,
    },
    body: JSON.stringify({ query, variables }),
  });
  const json = await res.json();
  if (json.errors?.length) {
    throw new Error(json.errors.map((e) => e.message).join("; "));
  }
  return json.data;
}

async function getTeamId(apiKey) {
  const data = await gql(
    apiKey,
    `query { teams { nodes { id key name } } }`,
  );
  const team = data.teams.nodes.find(
    (t) => t.key === TEAM_KEY || t.name.toLowerCase() === TEAM_KEY.toLowerCase(),
  );
  if (!team) throw new Error(`Team not found: ${TEAM_KEY}`);
  return team;
}

async function listCompletedIssues(apiKey, teamId) {
  const issues = [];
  let cursor = null;
  const query = `
    query($teamId: String!, $after: String) {
      team(id: $teamId) {
        issues(
          first: 100
          after: $after
          filter: { state: { type: { eq: "completed" } } }
        ) {
          pageInfo { hasNextPage endCursor }
          nodes { id identifier title }
        }
      }
    }
  `;
  for (;;) {
    const data = await gql(apiKey, query, { teamId, after: cursor });
    const page = data.team.issues;
    issues.push(...page.nodes);
    if (!page.pageInfo.hasNextPage) break;
    cursor = page.pageInfo.endCursor;
  }
  return issues;
}

async function deleteIssue(apiKey, id) {
  const data = await gql(
    apiKey,
    `mutation($id: String!) { issueDelete(id: $id) { success } }`,
    { id },
  );
  return data.issueDelete.success;
}

async function main() {
  const apiKey = getApiKey();
  if (!apiKey) {
    console.error("No Linear auth. Set LINEAR_API_KEY or run: linear auth login");
    process.exit(1);
  }

  const team = await getTeamId(apiKey);
  console.log(`Team: ${team.key} (${team.name})`);
  const issues = await listCompletedIssues(apiKey, team.id);
  console.log(`Found ${issues.length} completed issue(s).`);

  if (DRY_RUN) {
    for (const issue of issues.slice(0, 20)) {
      console.log(`  ${issue.identifier}  ${issue.title}`);
    }
    if (issues.length > 20) console.log(`  ... and ${issues.length - 20} more`);
    return;
  }

  let deleted = 0;
  let failed = 0;
  for (const issue of issues) {
    try {
      const ok = await deleteIssue(apiKey, issue.id);
      if (ok) {
        deleted += 1;
        console.log(`Deleted ${issue.identifier}`);
      } else {
        failed += 1;
        console.error(`Failed ${issue.identifier} (success=false)`);
      }
    } catch (err) {
      failed += 1;
      console.error(`Failed ${issue.identifier}: ${err.message}`);
    }
  }
  console.log(`Done. Deleted=${deleted} Failed=${failed}`);
}

main().catch((err) => {
  console.error(err.message || err);
  process.exit(1);
});
