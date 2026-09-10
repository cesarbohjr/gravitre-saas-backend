/**
 * Does the Next BFF layer leak authenticated AI data to anonymous callers?
 *
 * lib/backend-proxy.ts forwards `authorization` only when the client sent one and
 * injects no server credential, so the expectation is that FastAPI rejects every
 * one of these. This checks that expectation instead of assuming it.
 *
 * GET only, on purpose: this must not mutate production state.
 */
const ORIGIN = process.argv[2] || "https://gravitre.app"

const paths = [
  "/api/assistant/preferences",
  "/api/assistant/org-context",
  "/api/assistant/daily-briefing",
  "/api/assistant/business-signals",
  "/api/assistant/business-signals/priorities",
  "/api/conversations",
  "/api/voice/status",
  "/api/voice/library",
  "/api/voice/design",
]

// Sent deliberately: the proxy forwards this straight through from the client. If
// the backend scopes on it rather than on the JWT, an anonymous caller could name
// any tenant. A 401/403 here means the header is not load-bearing for auth.
const spoofedOrg = "00000000-0000-0000-0000-000000000000"

let leaks = 0
for (const path of paths) {
  for (const [label, headers] of [
    ["bare", {}],
    ["x-org-id spoof", { "x-org-id": spoofedOrg }],
  ]) {
    let line
    try {
      const res = await fetch(`${ORIGIN}${path}`, { headers, redirect: "manual" })
      const body = (await res.text()).slice(0, 120).replace(/\s+/g, " ")
      const rejected = res.status === 401 || res.status === 403
      if (!rejected) leaks++
      line = `${rejected ? "OK  " : "LEAK"} ${res.status} ${path} [${label}] ${body}`
    } catch (err) {
      line = `ERR  ${path} [${label}] ${err.message}`
    }
    console.log(line)
  }
}
console.log(
  leaks === 0
    ? "PASS - every probed AI route rejected the anonymous caller"
    : `FINDING - ${leaks} response(s) were not 401/403`,
)
