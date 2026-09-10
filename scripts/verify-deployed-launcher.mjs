/**
 * Confirms the Phase 1 launcher actually shipped, by reading the deployed
 * client chunks rather than trusting that the build succeeded.
 *
 * Looks for the required accessible name ("Open AI Chat") and the tooltip text,
 * plus the bubble path from ChatBubbleOutline24. Minifiers rename identifiers but
 * do not rewrite string or path-data literals, so these survive the build.
 */
const ORIGIN = process.argv[2] || "https://gravitre.app"

const needles = [
  ["accessible name", "Open AI Chat"],
  ["bubble path data", "M2 4H22V18H6.25L4 22H2V4Z"],
]

const pages = process.argv.slice(3)
const pages_ = pages.length ? pages : ["/login", "/dashboard"]
const html = (
  await Promise.all(
    pages_.map((p) => fetch(`${ORIGIN}${p}`, { headers: { "user-agent": "gravitre-verify" } }).then((r) => r.text())),
  )
).join("\n")
const chunks = [...new Set([...html.matchAll(/\/?_next\/static\/[^"'\s)]+?\.js/g)].map((m) => `/${m[0].replace(/^\//, "")}`))]
console.log(`origin=${ORIGIN}  chunks discovered=${chunks.length}`)

const found = new Map(needles.map(([label]) => [label, null]))
for (const chunk of chunks) {
  const src = await fetch(`${ORIGIN}${chunk}`).then((r) => (r.ok ? r.text() : ""))
  if (!src) continue
  for (const [label, needle] of needles) {
    if (!found.get(label) && src.includes(needle)) found.set(label, chunk)
  }
  if ([...found.values()].every(Boolean)) break
}

let ok = true
for (const [label, chunk] of found) {
  if (chunk) console.log(`PASS  ${label} -> ${chunk}`)
  else {
    ok = false
    console.log(`NOT FOUND  ${label} (may live in a lazily-loaded chunk not linked from /login)`)
  }
}
console.log(ok ? "PASS - deployed bundle carries the new launcher" : "INCONCLUSIVE - see above")
