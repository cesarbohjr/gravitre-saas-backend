#!/usr/bin/env node
/**
 * Clear placeholder due date on STA-258 (MCP cannot unset dueDate).
 * Usage: node scripts/clear-sta258-due-date.mjs
 */
import { spawnSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const WORKSPACE = process.env.LINEAR_WORKSPACE || "staqbot";
const ISSUE_ID = "STA-258";

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

async function linear(apiKey, query, variables) {
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
    throw new Error(JSON.stringify(json.errors, null, 2));
  }
  return json.data;
}

async function main() {
  const apiKey = getApiKey();
  if (!apiKey) {
    console.error("Set LINEAR_API_KEY/LINEAR_TOKEN or run linear auth login");
    process.exit(1);
  }

  const issue = await linear(
    apiKey,
    `query($id: String!) {
      issue(id: $id) { id identifier dueDate }
    }`,
    { id: ISSUE_ID },
  );
  console.log("Before:", issue.issue.identifier, "dueDate=", issue.issue.dueDate);

  const updated = await linear(
    apiKey,
    `mutation($id: String!) {
      issueUpdate(id: $id, input: { dueDate: null }) {
        success
        issue { identifier dueDate }
      }
    }`,
    { id: issue.issue.id },
  );

  console.log("After:", updated.issueUpdate.issue.identifier, "dueDate=", updated.issueUpdate.issue.dueDate);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
