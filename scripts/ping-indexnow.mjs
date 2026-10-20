#!/usr/bin/env node
/**
 * Submit ONLY successfully published, canonical gravitre.app URLs to IndexNow.
 * Requires an INDEXNOW_KEY and a publicly served https://gravitre.app/<key>.txt
 * holding that exact key. Never use preview URLs or request-time credentials.
 */
const key = (process.env.INDEXNOW_KEY || "").trim()
const inputs = process.argv.slice(2)
const host = "gravitre.app"
if (!key || !/^[a-zA-Z0-9-]{8,128}$/.test(key)) {
  console.error("INDEXNOW_KEY is missing or malformed. No URLs submitted.")
  process.exit(2)
}
if (!inputs.length) {
  console.error("Provide one or more published https://gravitre.app URLs.")
  process.exit(2)
}
const keyLocation = `https://${host}/${key}.txt`
const keyResponse = await fetch(keyLocation, { redirect: "error" })
if (!keyResponse.ok || (await keyResponse.text()).trim() !== key) {
  console.error("IndexNow domain key is not verified at", keyLocation)
  process.exit(2)
}
const urlList = []
for (const input of inputs) {
  const url = new URL(input)
  if (url.protocol !== "https:" || url.hostname !== host || url.search || url.hash) {
    throw new Error(`Not a canonical published Gravitre URL: ${input}`)
  }
  const check = await fetch(url.toString(), { redirect: "error" })
  if (!check.ok || !check.headers.get("content-type")?.includes("text/html")) {
    throw new Error(`Published URL not available as an HTML page: ${url.toString()} (HTTP ${check.status})`)
  }
  urlList.push(url.toString())
}
const response = await fetch("https://api.indexnow.org/indexnow", {
  method: "POST",
  headers: { "Content-Type": "application/json; charset=utf-8" },
  body: JSON.stringify({ host, key, keyLocation, urlList: [...new Set(urlList)] }),
})
if (![200, 202].includes(response.status)) {
  throw new Error(`IndexNow rejected request: HTTP ${response.status}`)
}
console.log(`IndexNow accepted ${new Set(urlList).size} published URL(s): HTTP ${response.status}`)
