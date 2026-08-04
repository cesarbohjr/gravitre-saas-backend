import { chromium } from "@playwright/test"

const b = await chromium.launch()
const p = await (
  await b.newContext({ viewport: { width: 1440, height: 900 }, colorScheme: "dark" })
).newPage()
p.on("pageerror", (e) => console.log("PAGEERROR:", e.message))

await p.goto("http://127.0.0.1:3000/e2e/shots/activity", { waitUntil: "domcontentloaded" })
await p.waitForTimeout(5000)

// The shot layout's stub is what AuthProvider consumes. Replay it exactly as
// supabase-js would and see what comes back.
console.log(
  "stubbed /auth/v1/user:",
  await p.evaluate(async () => {
    const r = await fetch("https://example.supabase.co/auth/v1/user")
    return `${r.status} ${(await r.text()).slice(0, 200)}`
  }),
)
// Does the loader belong to AppShell's auth gate, or to the Suspense fallback?
console.log(
  "loader labels:",
  await p.evaluate(() =>
    [...document.querySelectorAll("*")]
      .map((n) => n.getAttribute?.("aria-label"))
      .filter((v) => v && /Loading/i.test(v)),
  ),
)
await b.close()
