#!/usr/bin/env node
/**
 * Cowork audit validation script (steps 1–7).
 * Run from repo root: node scripts/validate-cowork-audit.mjs
 */
import fs from "node:fs"
import path from "node:path"
import { fileURLToPath } from "node:url"

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..")
const web = path.join(root, "apps", "web")
const backend = path.join(root, "backend")

const checks = []

function read(rel) {
  return fs.readFileSync(path.join(root, rel), "utf8")
}

function pass(id, label) {
  checks.push({ id, label, ok: true })
}

function fail(id, label, detail) {
  checks.push({ id, label, ok: false, detail })
}

function assertIncludes(id, label, file, needles) {
  const content = read(file)
  const missing = needles.filter((needle) => !content.includes(needle))
  if (missing.length === 0) pass(id, label)
  else fail(id, label, `Missing in ${file}: ${missing.join(", ")}`)
}

// 1. Welcome/marketing role + pack path exists
assertIncludes(
  "1",
  "Welcome flow supports Marketing role and pack slug",
  "apps/web/lib/welcome-flow.ts",
  ['id: "marketing"', "marketing-operations-pack", "packSlug"],
)

// 2. AI chat department + cross-department context
assertIncludes(
  "2",
  "AI workspace sends department and cross-department chat context",
  "apps/web/app/ai/_components/ai-workspace.tsx",
  ["selectedDepartment", "cross_department", "DEPARTMENT_OPTIONS"],
)
assertIncludes(
  "2b",
  "Assistant chat accepts department orchestration fields",
  "backend/app/routers/assistant.py",
  ["cross_department", "Department context"],
)

// 3. Execute suggested actions wired to backend (not toast-only)
assertIncludes(
  "3",
  "Execute actions call operator execute-action API",
  "apps/web/lib/execute-action-service.ts",
  ["/api/operators/execute-action", "executeSuggestedAction"],
)
assertIncludes(
  "3b",
  "Execute results panel uses real action handlers",
  "apps/web/app/ai/_components/ai-execute-results.tsx",
  ["executeSuggestedAction", "executePlanApproval", "runAutoFix"],
)

// 4. Lite seat assign API + UI
assertIncludes(
  "4",
  "Department member assign API exists",
  "backend/app/routers/settings.py",
  ["/lite-seats/members", "add_department_member_route"],
)
assertIncludes(
  "4b",
  "Settings UI assigns Lite seats by email",
  "apps/web/app/settings/page.tsx",
  ["addDepartmentMember", "Assign seat"],
)

// 5. Assignments fail loudly (no silent demo fallback)
assertIncludes(
  "5",
  "Assignment create throws on API failure",
  "apps/web/lib/assignments.ts",
  ["throw new Error", "Assignment could not be created"],
)

// 6. Billing charts derive from API usage (no hardcoded 12450 runs)
const billing = read("apps/web/app/settings/billing/page.tsx")
if (billing.includes("12450")) {
  fail("6", "Billing page removed demo workflow usage constants", "Still contains 12450")
} else if (billing.includes("buildUsageForecast")) {
  pass("6", "Billing forecast uses API-driven buildUsageForecast")
} else {
  fail("6", "Billing forecast uses API-driven buildUsageForecast", "buildUsageForecast not found")
}

// 7. Operator context resolves from connected connectors
assertIncludes(
  "7",
  "Operator context resolves from live connectors",
  "apps/web/lib/operator-context.ts",
  ["/api/connectors", "resolveOperatorActiveContext"],
)
assertIncludes(
  "7b",
  "Execute mode uses resolved operator context",
  "apps/web/app/ai/_components/ai-workspace.tsx",
  ["resolveOperatorActiveContext", "operatorContextRef"],
)

const failed = checks.filter((check) => !check.ok)
for (const check of checks) {
  const mark = check.ok ? "PASS" : "FAIL"
  console.log(`${mark} [${check.id}] ${check.label}${check.detail ? ` — ${check.detail}` : ""}`)
}

if (failed.length > 0) {
  console.error(`\n${failed.length} validation check(s) failed.`)
  process.exit(1)
}

console.log(`\nAll ${checks.length} cowork audit validation checks passed.`)
