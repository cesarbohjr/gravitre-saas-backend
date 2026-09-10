/**
 * Which voice WebSocket origin does the DEPLOYED bundle actually dial?
 *
 * resolvePipecatWsOrigin() falls back through NEXT_PUBLIC_VOICE_WS_BASE ->
 * status.pipecat_ws_hint -> PRODUCTION_API_URL. NEXT_PUBLIC_* is inlined at build
 * time, so the only way to know what shipped is to read the shipped chunks.
 *
 * Run: node scripts/probe-deployed-ws-origin.mjs [origin]
 */
const origin = process.argv[2] || "https://gravitre.app"
const NEEDLES = [
  "api.gravitre.app",
  "/api/voice/pipecat/ws",
  "pipecat_ws_hint",
  "retries-exhausted",
]

async function text(url) {
  const res = await fetch(url, { redirect: "follow" })
  if (!res.ok) throw new Error(String(res.status))
  return res.text()
}

const chunks = new Set()
for (const page of ["/ai", "/", "/agents", "/login"]) {
  try {
    const html = await text(origin + page)
    for (const m of html.matchAll(/\/_next\/static\/[^"'\s\\)]+?\.js/g)) chunks.add(m[0])
  } catch {
    /* page not public; skip */
  }
}

console.log(`Scanning ${chunks.size} chunks from ${origin}`)

const hits = new Map()
// Any other wss:// or https:// origin referenced near the voice path is worth seeing.
const origins = new Set()

for (const chunk of chunks) {
  let body
  try {
    body = await text(origin + chunk)
  } catch {
    continue
  }
  for (const needle of NEEDLES) {
    if (body.includes(needle) && !hits.has(needle)) hits.set(needle, chunk)
  }
  if (body.includes("/api/voice/pipecat/ws")) {
    for (const m of body.matchAll(/(wss?|https?):\/\/[a-z0-9.-]+\.[a-z]{2,}/gi)) {
      origins.add(m[0])
    }
  }
}

for (const needle of NEEDLES) {
  const where = hits.get(needle)
  console.log(where ? `FOUND  ${needle}  in ${where}` : `absent ${needle}`)
}

console.log("\nOrigins referenced in the chunk that contains the voice ws path:")
for (const o of [...origins].sort()) console.log(`  ${o}`)
