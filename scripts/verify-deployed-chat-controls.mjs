/**
 * Confirms the consolidated window controls actually reached production, rather
 * than trusting a green local suite.
 *
 * Looks for the marker attribute the shared component stamps on every control and
 * for the label that only exists because the embedded /ai surface was given an
 * exit. Finding the latter is the specific proof that the dead-end fix shipped.
 *
 * Run: node scripts/verify-deployed-chat-controls.mjs
 */

const BASE = process.env.BASE_URL || "https://gravitre.app"
const PAGES = ["/login", "/dashboard"]

const NEEDLES = [
  ["data-chat-window-control", "shared control marker"],
  ["Open as floating window", "embedded /ai surface has an exit"],
  ["Minimize to helper", "single name for the minimize action"],
  ["Collapse to floating window", "expanded/fullscreen keeps its float route"],
]

async function chunkUrls() {
  const found = new Set()
  for (const page of PAGES) {
    const res = await fetch(`${BASE}${page}`, { redirect: "follow" })
    const html = await res.text()
    // Next serves these from _next/static/immutable/chunks, not _next/static/chunks.
    for (const m of html.matchAll(/\/?_next\/static\/[^"'\s)]+?\.js/g)) {
      found.add(new URL(m[0].startsWith("/") ? m[0] : `/${m[0]}`, BASE).toString())
    }
  }
  return [...found]
}

const urls = await chunkUrls()
console.log(`base=${BASE} chunks=${urls.length}`)
if (urls.length === 0) {
  console.log("FAIL could not find any chunks to inspect")
  process.exit(1)
}

const hits = new Map(NEEDLES.map(([needle]) => [needle, []]))
for (const url of urls) {
  const res = await fetch(url)
  if (!res.ok) continue
  const body = await res.text()
  for (const [needle] of NEEDLES) {
    if (body.includes(needle)) hits.get(needle).push(url.split("/").pop())
  }
}

let failures = 0
for (const [needle, description] of NEEDLES) {
  const where = hits.get(needle)
  if (where.length) {
    console.log(`PASS  ${description}\n        "${needle}" in ${where.join(", ")}`)
  } else {
    console.log(`FAIL  ${description}\n        "${needle}" not found in any deployed chunk`)
    failures += 1
  }
}

console.log(failures === 0 ? "\nRESULT: PASS" : `\nRESULT: ${failures} FAILURE(S)`)
process.exit(failures ? 1 : 0)
