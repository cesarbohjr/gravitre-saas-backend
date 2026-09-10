#!/usr/bin/env node
/**
 * Fail CI when production chat/voice UI can render generic "is thinking"
 * copy or interpolate unsanitized intelligence fields (answerExplanation).
 *
 * Complements the sanitizer mutation tests: this catches a future surface
 * that bypasses deriveAgentStatusLabel / sanitizeUserActivityLabel.
 */
import { readdirSync, readFileSync, statSync } from "node:fs"
import { join, relative, dirname } from "node:path"
import { fileURLToPath } from "node:url"

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..")
const WEB = join(WEB_ROOT(), "apps", "web")

function WEB_ROOT() {
  return ROOT
}

const ALLOW_THINKING = new Set([
  "components/gravitre/assistant/gravitre-chat-avatar.tsx",
  "components/gravitre/assistant/thinking-loader.tsx",
  "components/gravitre/assistant/chat-transcript.tsx",
  "app/e2e/shots/avatar-states/page.tsx",
])

const ALLOW_DIR = [
  "components/marketing/",
  "app/e2e/",
  "app/dev/",
]

function walk(dir, out = []) {
  for (const name of readdirSync(dir)) {
    if (name === "node_modules" || name === ".next" || name === "dist") continue
    const p = join(dir, name)
    const st = statSync(p)
    if (st.isDirectory()) walk(p, out)
    else if (/\.(tsx|ts|jsx)$/.test(name)) out.push(p)
  }
  return out
}

const files = walk(join(WEB, "app")).concat(walk(join(WEB, "components")))
const failures = []

for (const file of files) {
  const rel = relative(WEB, file).replace(/\\/g, "/")
  if (rel.includes("__tests__") || rel.includes(".test.")) continue
  if (ALLOW_DIR.some((prefix) => rel.startsWith(prefix))) continue
  const src = readFileSync(file, "utf8")

  if (!ALLOW_THINKING.has(rel) && /is thinking/i.test(src)) {
    failures.push(`${rel}: generic "is thinking" copy — use deriveAgentStatusLabel / SAFE_STATUS_FALLBACK`)
  }

  if (
    /\{[^}]*answerExplanation/.test(src) &&
    !/sanitizeUserActivityLabel|deriveAgentStatusLabel/.test(src)
  ) {
    failures.push(`${rel}: interpolates answerExplanation without the AI State sanitizer`)
  }
}

if (failures.length) {
  console.error("User-facing status leak guard failed:\n" + failures.map((row) => `  - ${row}`).join("\n"))
  process.exit(1)
}

console.log("User-facing status leak guard: PASS")
