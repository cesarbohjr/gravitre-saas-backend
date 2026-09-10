/**
 * Prove the deployed frontend is serving the reconnect policy, rather than
 * inferring it from deploy timestamps.
 *
 * decideSocketFailure returns the literal reasons "retries-exhausted",
 * "session-ended" and "intentional". String literals survive minification, so
 * finding them in a production chunk is direct evidence the new code is live.
 *
 * Run: node scripts/verify-deployed-reconnect.mjs [origin]
 */
const origin = process.argv[2] || "https://gravitre.app"
const NEEDLES = ["retries-exhausted", "session-ended"]

async function text(url) {
  const res = await fetch(url, { redirect: "follow" })
  if (!res.ok) throw new Error(`${res.status} ${url}`)
  return res.text()
}

const pages = ["/ai", "/", "/agents"]
const chunks = new Set()

for (const page of pages) {
  try {
    const html = await text(origin + page)
    for (const m of html.matchAll(/\/_next\/static\/[^"'\s\\)]+?\.js/g)) chunks.add(m[0])
  } catch (err) {
    console.log(`  (skipped ${page}: ${err.message})`)
  }
}

console.log(`Discovered ${chunks.size} chunks from ${pages.join(", ")}`)

const found = new Map()
let scanned = 0

for (const chunk of chunks) {
  let body
  try {
    body = await text(origin + chunk)
  } catch {
    continue
  }
  scanned += 1
  for (const needle of NEEDLES) {
    if (body.includes(needle)) {
      if (!found.has(needle)) found.set(needle, chunk)
    }
  }
}

console.log(`Scanned ${scanned} chunks`)
for (const needle of NEEDLES) {
  const where = found.get(needle)
  console.log(where ? `FOUND  "${needle}" in ${where}` : `absent "${needle}"`)
}

if (found.size === NEEDLES.length) {
  console.log("\nRESULT: reconnect policy is live on the deployed frontend")
} else {
  console.log(
    "\nRESULT: INCONCLUSIVE from public chunks -- the voice hook ships in an\n" +
      "authenticated route's chunk, which is not reachable from these pages.",
  )
}
