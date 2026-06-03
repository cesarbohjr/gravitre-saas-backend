#!/usr/bin/env node
/**
 * Create one Linear issue: platform HubSpot OAuth deployment checklist (pre-STA-14).
 *
 * Usage:
 *   $env:LINEAR_API_KEY="lin_api_..."
 *   node scripts/create-hubspot-platform-setup-linear-issue.mjs
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
const API_KEY = process.env.LINEAR_API_KEY || process.env.LINEAR_TOKEN;
const PROJECT = "Tier 1 Integration Platform";
const PARENT_EPIC = process.env.LINEAR_HUBSPOT_EPIC || "STA-7";

const TITLE = "[T1-004a] Platform setup: HubSpot OAuth app & deployment secrets";
const DESCRIPTION = `**Audience:** Gravitre platform operator (deploy / DevOps). **Not** a per-customer task.

End users only click **Connect HubSpot** in the app. This issue is the **one-time per environment** setup so native OAuth (STA-13) and token lifecycle (STA-14) work.

## Checklist

### 1. HubSpot developer app (one per environment)
- [ ] Create a HubSpot app in [HubSpot Developer](https://developers.hubspot.com/)
- [ ] Note **Client ID** and **Client secret** (secret never in git or chat)
- [ ] Optional: separate sandbox app for non-prod

### 2. Redirect URLs (must match exactly)
Register in the HubSpot app:
- [ ] \`{API_PUBLIC_URL}/api/connectors/oauth/hubspot/callback\`

Examples:
- Local API: \`http://localhost:8000/api/connectors/oauth/hubspot/callback\`
- Production: \`https://api.<your-domain>/api/connectors/oauth/hubspot/callback\`

### 3. Backend environment variables (Railway / host secrets)
- [ ] \`HUBSPOT_CLIENT_ID\` — from HubSpot app
- [ ] \`HUBSPOT_CLIENT_SECRET\` — from HubSpot app
- [ ] \`CONNECTOR_SECRETS_ENCRYPTION_KEY\` — Fernet key (\`Fernet.generate_key()\`); required to store OAuth tokens encrypted in \`connector_secrets\`
- [ ] \`NEXT_PUBLIC_APP_URL\` — frontend base (post-auth redirect), e.g. \`https://app.gravitre.app\`
- [ ] \`API_PUBLIC_URL\` — public API base for OAuth callback (if API host ≠ app host)

See \`backend/.env.example\`.

### 4. Smoke test
- [ ] Restart API after env changes
- [ ] Admin → Connectors → **Connect with HubSpot** → complete HubSpot login
- [ ] Connector shows healthy / connected; \`POST /api/connectors/{id}/test\` succeeds

## Code references
- OAuth routes: \`backend/app/routers/connector_oauth.py\`
- HubSpot OAuth: \`backend/app/connectors/hubspot_oauth.py\`
- Connect UI: \`apps/web/app/connectors/page.tsx\`

## Linear links
- **Depends on:** [STA-13](https://linear.app/staqbot/issue/STA-13) (T1-004 — Real connector OAuth UX) — code shipped
- **Blocks:** [STA-14](https://linear.app/staqbot/issue/STA-14) (T1-005 — HubSpot OAuth + token lifecycle)

## Note on Nango
We are **not** using Nango for HubSpot; tokens stay in \`connector_secrets\` with native OAuth. Nango connection IDs are out of scope for this track.
`;

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

function ensureLabel(team, name) {
  try {
    run(
      `${LINEAR} label create -n ${shQuote(name)} -t ${shQuote(team)} -c "#5E6AD2"`,
      { capture: true },
    );
  } catch (e) {
    const msg = e.message.toLowerCase();
    if (!msg.includes("already") && !msg.includes("duplicate") && !msg.includes("exists")) {
      throw e;
    }
  }
}

function main() {
  if (!API_KEY) {
    console.error("LINEAR_API_KEY is required. See scripts/create-tier1-linear-issues.mjs");
    process.exit(1);
  }
  process.env.LINEAR_API_KEY = API_KEY;

  let team = process.env.LINEAR_TEAM;
  if (!team) {
    const teamsOut = run(`${LINEAR} team list`, { capture: true });
    team = teamsOut.match(/\b(STA|[A-Z]{2,6})\b/)?.[1] ?? "STA";
  }

  for (const label of ["tier-1", "hubspot", "ops", "platform"]) {
    ensureLabel(team, label);
  }

  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "linear-hubspot-setup-"));
  const descFile = path.join(tmpDir, "desc.md");
  fs.writeFileSync(descFile, DESCRIPTION, "utf-8");

  const parts = [
    LINEAR,
    "issue create",
    "--no-interactive",
    `-t ${shQuote(TITLE)}`,
    `--description-file ${shQuote(descFile)}`,
    `--team ${shQuote(team)}`,
    `--parent ${shQuote(PARENT_EPIC)}`,
    `--project ${shQuote(PROJECT)}`,
    "-p 1",
    "--estimate 1",
    '-l "tier-1"',
    '-l "hubspot"',
    '-l "ops"',
    '-l "platform"',
  ];

  console.log("Creating Linear issue...");
  const output = run(parts.join(" "), { capture: true });
  fs.rmSync(tmpDir, { recursive: true, force: true });

  const id = parseIssueId(output);
  if (!id) {
    console.error(output);
    process.exit(1);
  }
  console.log(`Created: ${id}`);
  console.log(`https://linear.app/staqbot/issue/${id}`);
}

main();
