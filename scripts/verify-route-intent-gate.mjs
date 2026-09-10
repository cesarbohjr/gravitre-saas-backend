/**
 * Live proof that POST /api/ai/route-intent rejects unauthenticated callers.
 *
 * Sends an empty body deliberately. The gate runs before the body is read, so a
 * 401 (rather than the old 400 "prompt required") is the evidence that the
 * session check is what answered -- and it means no model call is billed either
 * way.
 */
const ORIGIN = process.argv[2] || "https://gravitre.app"
const url = `${ORIGIN}/api/ai/route-intent`

const res = await fetch(url, {
  method: "POST",
  headers: { "content-type": "application/json" },
  body: "{}",
})
const text = await res.text()
console.log(`POST ${url}`)
console.log(`status=${res.status} ${res.statusText}`)
console.log(`x-vercel-id=${res.headers.get("x-vercel-id") ?? "(none)"}`)
console.log(`body=${text.slice(0, 300)}`)
console.log(
  res.status === 401
    ? "PASS - unauthenticated request rejected by the session gate"
    : `FAIL - expected 401, got ${res.status}`,
)
