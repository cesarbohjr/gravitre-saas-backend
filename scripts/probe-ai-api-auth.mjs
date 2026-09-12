/**
 * Do the protected AI endpoints actually reject unauthenticated requests?
 *
 * Section 2 of the chat/voice brief requires enforcement beyond CSS. Hiding a
 * launcher proves nothing if the endpoints behind it answer to anyone, so this
 * asks them directly with no credentials.
 *
 * Anything that is not 401/403 (or a redirect to login) is a finding.
 *
 * Run: node scripts/probe-ai-api-auth.mjs [origin]
 */
const origin = process.argv[2] || "https://gravitre.app"

const TARGETS = [
  ["GET", "/api/assistant/org-context"],
  ["GET", "/api/assistant/daily-briefing"],
  ["GET", "/api/assistant/preferences"],
  ["GET", "/api/assistant/business-signals"],
  ["POST", "/api/ai/route-intent", { text: "probe" }],
  ["GET", "/api/agents"],
  ["GET", "/api/voice/status"],
  ["POST", "/api/voice/token", {}],
  ["GET", "/api/conversations"],
  ["GET", "/api/settings/organization"],
]

const OK = new Set([401, 403])
const findings = []

for (const [method, path, body] of TARGETS) {
  const url = origin + path
  let status
  let snippet = ""
  try {
    const res = await fetch(url, {
      method,
      redirect: "manual",
      headers: body ? { "content-type": "application/json" } : undefined,
      body: body ? JSON.stringify(body) : undefined,
    })
    status = res.status
    snippet = (await res.text()).slice(0, 110).replace(/\s+/g, " ")
  } catch (err) {
    status = "network-error"
    snippet = err.message
  }

  const redirectToLogin =
    typeof status === "number" && status >= 300 && status < 400
  const verdict = OK.has(status)
    ? "REJECTED (good)"
    : redirectToLogin
      ? "REDIRECT (acceptable)"
      : status === 404
        ? "404 (route absent here)"
        : "!! REACHABLE UNAUTHENTICATED"

  if (verdict.startsWith("!!")) findings.push(`${method} ${path} -> ${status}`)
  console.log(`${String(status).padEnd(14)} ${verdict.padEnd(30)} ${method} ${path}`)
  if (verdict.startsWith("!!")) console.log(`               body: ${snippet}`)
}

console.log()
if (findings.length) {
  console.log(`RESULT: ${findings.length} endpoint(s) answered without credentials:`)
  for (const f of findings) console.log(`  ${f}`)
  process.exitCode = 1
} else {
  console.log("RESULT: every probed AI endpoint refused an unauthenticated request")
}
