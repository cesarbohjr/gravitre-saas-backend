// Slice 1 browser validation. Drives /dev/slice-1-workspace (real bridges,
// shells and provider with fixture props) in headless Chromium/Edge and
// records pass/fail with evidence. Nothing here injects attributes into the
// page, so hydration results are not polluted by tooling.
//
// Usage (playwright-core must be resolvable, e.g. run from a temp dir that has it):
//   node validate-slice1.mjs <base-url> <out-dir> [browser-executable]
import { chromium } from "playwright-core"
import { writeFileSync } from "node:fs"
import { join } from "node:path"

const BASE = process.argv[2] ?? "http://127.0.0.1:3010"
const OUT = process.argv[3] ?? "."
const EXE = process.argv[4] ?? "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"
const URL = `${BASE}/dev/slice-1-workspace`
const PREF = "gravitre.wm.preferred-mode.v1"
const COMPOSITION = "gravitre.ai.composition.v1"

const results = []
function record(area, check, pass, evidence) {
  results.push({ area, check, result: pass ? "PASS" : "FAIL", evidence })
  console.log(`${pass ? "PASS" : "FAIL"} [${area}] ${check} — ${evidence}`)
}

const browser = await chromium.launch({ executablePath: EXE, headless: true })

async function open(viewport, { seed = {}, reducedMotion = "no-preference", url = URL } = {}) {
  const ctx = await browser.newContext({ viewport, reducedMotion })
  await ctx.addInitScript((s) => {
    for (const [k, v] of Object.entries(s)) window.localStorage.setItem(k, v)
  }, seed)
  const page = await ctx.newPage()
  page.setDefaultTimeout(60000)
  const logs = []
  page.on("console", (m) => {
    if (m.type() === "error" || m.type() === "warning") logs.push(m.text())
  })
  page.on("pageerror", (e) => logs.push(`pageerror: ${e.message}`))
  await page.goto(url, { waitUntil: "domcontentloaded", timeout: 120000 })
  await page.waitForSelector("[data-slice1-mode], [data-slice0-wm-shell]")
  // Wait for hydration: the mode history is only filled by a client effect.
  if (url === URL) await page.waitForFunction(() => /Mode history: \w/.test(document.body.innerText), null, { timeout: 60000 })
  await page.waitForTimeout(500)
  return { ctx, page, logs }
}

const hydrationErrors = (logs) => logs.filter((l) => /hydrat|did not match|server rendered/i.test(l))
const btn = (page, name) => page.getByRole("button", { name, exact: true })
// Let enter transitions (opacity/scale, MOTION.major = 0.4s) settle so shots show the resting state.
const shot = async (page, name) => {
  await page.waitForTimeout(700)
  await page.screenshot({ path: join(OUT, name) })
}
const mode = (page) => page.getAttribute("[data-slice1-mode]", "data-slice1-mode")
async function identity(page) {
  return {
    instance: await page.getAttribute("[data-slice1-instance-stable]", "data-slice1-instance-stable"),
    messages: await page.getAttribute("[data-slice1-messages-stable]", "data-slice1-messages-stable"),
  }
}
async function scenario(page, name) {
  await page.getByRole("group", { name: "Runtime scenario" }).getByRole("button", { name, exact: true }).click()
}

// ── Hydration ──────────────────────────────────────────────────────────────
for (const [label, seed, url] of [
  ["slice-1 preview, no stored preference", {}, URL],
  ["slice-1 preview, stored preference=docked", { [PREF]: "docked", [COMPOSITION]: "work" }, URL],
  ["slice-0 foundation, stored preference=expanded", { [PREF]: "expanded" }, `${BASE}/dev/slice-0-foundation`],
]) {
  const { ctx, page, logs } = await open({ width: 1440, height: 900 }, { seed, url })
  await page.reload({ waitUntil: "domcontentloaded", timeout: 120000 })
  await page.waitForSelector("[data-slice1-mode], [data-slice0-wm-shell]")
  await page.waitForTimeout(1500)
  const errs = hydrationErrors(logs)
  record("hydration", label, errs.length === 0, errs.length ? errs[0].slice(0, 200) : `0 hydration console errors over 2 loads`)
  if (url.includes("slice-0")) {
    await page
      .waitForFunction(() => document.querySelector("[data-slice0-wm-shell]")?.getAttribute("data-wm-mode-source") !== "contextual", null, { timeout: 60000 })
      .catch(() => {})
    const lateErrs = hydrationErrors(logs)
    record("hydration", "slice-0: still no hydration errors once hydrated", lateErrs.length === 0, lateErrs.length ? lateErrs[0].slice(0, 200) : "0")
    const source = await page.getAttribute("[data-slice0-wm-shell]", "data-wm-mode-source")
    record("hydration", "slice-0 preference applied after hydration", source === "preference", `data-wm-mode-source=${source}`)
  }
  await ctx.close()
}

// ── Desktop 1440×900: full transition walk ────────────────────────────────
{
  const { ctx, page, logs } = await open({ width: 1440, height: 900 }, { seed: { [PREF]: "docked" } })
  await btn(page, "Open AI Chat (fixture launcher)").click()
  await page.waitForSelector('[data-gravitre-wm-placement="docked"]')
  await page.waitForTimeout(900)
  record("wm", "launcher opens at remembered preference (docked)", (await mode(page)) === "docked", `mode=${await mode(page)}`)

  const bodyPad = await page.evaluate(() => getComputedStyle(document.body).paddingRight)
  const dockBox = await page.locator('[data-gravitre-wm-placement="docked"]').boundingBox()
  const fieldBox = await page.getByPlaceholder("Type here while the workspace is docked").boundingBox()
  await page.getByPlaceholder("Type here while the workspace is docked").fill("typed beside the dock")
  const typed = await page.getByPlaceholder("Type here while the workspace is docked").inputValue()
  record(
    "wm",
    "docked keeps page usable",
    bodyPad !== "0px" && fieldBox.x + fieldBox.width <= dockBox.x && typed === "typed beside the dock",
    `body padding-right=${bodyPad}; field right=${Math.round(fieldBox.x + fieldBox.width)} ≤ dock left=${Math.round(dockBox.x)}; typed ok=${typed === "typed beside the dock"}`,
  )
  await shot(page, "01-desktop-light-docked.png")

  await scenario(page, "needs approval")
  await page.waitForSelector('[data-gravitre-ai-runtime-state="needs_approval"]')
  const approve = page.getByRole("button", { name: /approve and run/i })
  const approveVisible = await approve.isVisible()
  if (approveVisible) await approve.click()
  const logText = await page.locator('[aria-label="Fixture event log"]').textContent().catch(() => "")
  record(
    "runtime",
    "needs approval: status line + real Approve button visible in docked window",
    approveVisible && /Approve clicked/.test(logText ?? "") && /nothing executed/.test(logText ?? ""),
    `status=needs_approval; approve visible=${approveVisible}; log="${(logText ?? "").slice(0, 60)}"`,
  )
  await shot(page, "02-desktop-light-docked-needs-approval.png")

  await btn(page, "Undock to floating window").click()
  await page.waitForSelector('[data-gravitre-wm-placement="window"][data-gravitre-wm-variant="floating"]')
  const bodyPadAfter = await page.evaluate(() => getComputedStyle(document.body).paddingRight)
  record("wm", "undock → floating window, page space released", bodyPadAfter === "0px", `mode=${await mode(page)}; body padding-right=${bodyPadAfter}`)
  await shot(page, "03-desktop-light-floating.png")

  // The expanded shell overlays the page, so scenarios change while windowed.
  await scenario(page, "completed")
  await btn(page, "Expand").click()
  await page.waitForSelector('[data-gravitre-ai-shell-mode="expanded"]')
  await page.waitForSelector('[data-gravitre-ai-composition-body="split"]')
  record("composition", "work exists → Split by default", true, `composition=split, runtime=completed`)
  await shot(page, "04-desktop-light-expanded-split.png")

  await page.locator("[data-gravitre-ai-composition] button:visible", { hasText: "Work" }).click()
  await page.waitForSelector('[data-gravitre-ai-composition-body="work"]')
  record("composition", "Work view selectable and remembered", (await page.evaluate((k) => localStorage.getItem(k), COMPOSITION)) === "work", `stored=${await page.evaluate((k) => localStorage.getItem(k), COMPOSITION)}`)
  await shot(page, "05-desktop-light-expanded-work.png")

  await btn(page, "Collapse to floating window").click()
  await page.waitForSelector("[data-gravitre-float-workspace]")
  record("wm", "collapse expanded ? floating window", ["float", "floating"].includes(await mode(page)), `mode=${await mode(page)}`)
  await scenario(page, "needs approval")
  await btn(page, "Expand").click()
  await page.waitForSelector('[data-gravitre-ai-shell-mode="expanded"]')
  const compWithApproval = await page.getAttribute("[data-gravitre-ai-composition-body]", "data-gravitre-ai-composition-body")
  const approveInShell = await page.getByRole("button", { name: /approve and run/i }).isVisible()
  record(
    "composition",
    "approval never hidden: remembered Work falls back to Split",
    compWithApproval === "split" && approveInShell,
    `composition=${compWithApproval} with needs_approval; Approve visible=${approveInShell}`,
  )

  await btn(page, "Fullscreen").click()
  await page.waitForSelector('[data-gravitre-ai-shell-mode="fullscreen"]')
  const dialog = page.locator('[data-gravitre-ai-shell][role="dialog"]')
  const modal = await dialog.getAttribute("aria-modal")
  const exitVisible = await btn(page, "Exit fullscreen").isVisible()
  const reduceVisible = await btn(page, "Collapse to floating window").isVisible()
  record("wm", "fullscreen is a modal dialog with exit and reduce controls", modal === "true" && exitVisible && reduceVisible, `aria-modal=${modal}; exit=${exitVisible}; reduce=${reduceVisible}`)
  let escaped = 0
  for (let i = 0; i < 25; i++) {
    await page.keyboard.press("Tab")
    const inside = await page.evaluate(() => Boolean(document.activeElement?.closest("[data-gravitre-ai-shell]")))
    if (!inside) escaped++
  }
  record("a11y", "fullscreen focus trap holds over 25 Tabs", escaped === 0, `focus left dialog ${escaped} times`)
  await shot(page, "06-desktop-light-fullscreen.png")
  await page.keyboard.press("Escape")
  await page.waitForSelector('[data-gravitre-ai-shell-mode="expanded"]')
  record("wm", "Escape returns from fullscreen to expanded", true, `mode=${await mode(page)}`)

  await btn(page, "Minimize to helper").click()
  await page.waitForSelector("[data-slice1-preview-launcher]")
  record("wm", "minimize → launcher visible (no trapped window)", (await mode(page)) === "helper", `mode=${await mode(page)}; stored pref=${await page.evaluate((k) => localStorage.getItem(k), PREF)}`)
  await btn(page, "Open AI Chat (fixture launcher)").click()
  await page.waitForSelector('[data-gravitre-ai-shell-mode="expanded"]')
  record("wm", "restore returns to the mode minimized from", (await mode(page)) === "expanded", `mode=${await mode(page)}`)

  await btn(page, "Dock to side").click()
  await page.waitForSelector('[data-gravitre-wm-placement="docked"]')
  record("wm", "dock from expanded", (await mode(page)) === "docked", `mode=${await mode(page)}`)

  const id = await identity(page)
  const history = await page.locator("text=Mode history:").textContent()
  record("identity", "provider instance + messages array unchanged across all transitions", id.instance === "true" && id.messages === "true", `instance-stable=${id.instance}; messages-stable=${id.messages}; ${history}`)
  const conversationRegions = await page.locator('[data-gravitre-float-workspace], [data-gravitre-ai-shell], [data-gravitre-mobile-sheet-mode]').count()
  record("identity", "exactly one workspace surface mounted", conversationRegions === 1, `surfaces=${conversationRegions}`)

  // Dark theme.
  await page.getByRole("button", { name: "Light", exact: true }).click()
  await page.waitForTimeout(300)
  await scenario(page, "partial")
  await shot(page, "07-desktop-dark-docked-partial.png")
  await scenario(page, "failed")
  await btn(page, "Expand").click()
  await page.waitForSelector('[data-gravitre-ai-shell-mode="expanded"]')
  await shot(page, "08-desktop-dark-expanded-failed.png")
  record("runtime", "failed state from executionResult.success=false", (await page.getAttribute("[data-gravitre-ai-runtime-state]", "data-gravitre-ai-runtime-state")) === "failed", "status=failed")

  record("console", "no page errors during desktop walk", logs.filter((l) => l.startsWith("pageerror")).length === 0, `${logs.filter((l) => l.startsWith("pageerror")).length} page errors`)
  await ctx.close()
}

// ── Keyboard + inspector + visible focus ───────────────────────────────────
{
  const { ctx, page } = await open({ width: 1440, height: 900 })
  await btn(page, "Open AI Chat (fixture launcher)").focus()
  await page.keyboard.press("Enter")
  await page.waitForSelector("[data-gravitre-float-workspace]")
  record("a11y", "launcher opens with Enter", true, `mode=${await mode(page)} (contextual default, no preference)`)
  const controls = page.locator("[data-gravitre-float-workspace] button")
  const labels = await controls.evaluateAll((els) => els.map((e) => e.getAttribute("aria-label")).filter(Boolean))
  record("a11y", "window controls have accessible names", labels.length >= 4, labels.join(" | "))
  await controls.first().focus()
  await page.keyboard.press("Shift+Tab")
  await page.keyboard.press("Tab")
  await page.waitForTimeout(400)
  const ring = await page.evaluate(() => {
    const el = document.activeElement
    const s = getComputedStyle(el)
    const visibleShadow = s.boxShadow.split(/,(?![^(]*\))/).some((part) => !/rgba\(\s*0,\s*0,\s*0,\s*0\s*\)|^\s*none\s*$/.test(part))
    return { label: el.getAttribute("aria-label"), focusVisible: el.matches(":focus-visible"), outline: s.outlineStyle, visibleShadow }
  })
  record(
    "a11y",
    "visible focus on window control",
    ring.focusVisible && (ring.outline !== "none" || ring.visibleShadow),
    `focused="${ring.label}"; :focus-visible=${ring.focusVisible}; outline=${ring.outline}; visible ring shadow=${ring.visibleShadow}`,
  )
  await shot(page, "13-desktop-light-keyboard-focus.png")

  await btn(page, "Minimize to helper").click()
  await page.waitForSelector("[data-slice1-preview-launcher]")
  await btn(page, "Evidence").click()
  await page.waitForSelector('[role="dialog"][data-gravitre-inspector="evidence"]')
  const labelled = await page.getAttribute('[data-gravitre-inspector="evidence"]', "aria-labelledby")
  await page.keyboard.press("Escape")
  await page.waitForSelector('[data-gravitre-inspector]', { state: "detached" })
  const focused = await page.evaluate(() => document.activeElement?.textContent)
  record("a11y", "inspector: dialog, Escape closes, focus returns to opener", Boolean(labelled) && focused === "Evidence", `aria-labelledby=${labelled}; focus after close="${focused}"`)
  await ctx.close()
}

// ── Reduced motion ─────────────────────────────────────────────────────────
{
  const { ctx, page } = await open({ width: 1440, height: 900 }, { reducedMotion: "reduce" })
  await btn(page, "Open AI Chat (fixture launcher)").click()
  await page.waitForSelector("[data-gravitre-float-workspace]")
  const layout = await page.getAttribute("[data-gravitre-float-workspace]", "data-gravitre-workspace-layout-id")
  await scenario(page, "streaming")
  const pingAnim = await page.evaluate(() => {
    const el = document.querySelector("[data-gravitre-ai-runtime-state] .motion-safe\\:animate-ping")
    return el ? getComputedStyle(el).animationName : "absent"
  })
  record("a11y", "reduced motion: no shared-layout animation, no live pulse", layout === "reduced-motion" && (pingAnim === "none" || pingAnim === "absent"), `layout-id=${layout}; pulse animation=${pingAnim}`)
  await ctx.close()
}

// ── Narrow desktop, tablet, mobile ─────────────────────────────────────────
for (const [label, viewport, file] of [
  ["narrow desktop 1024×768", { width: 1024, height: 768 }, "09-narrow-desktop-light-docked.png"],
  ["tablet 834×1112", { width: 834, height: 1112 }, "10-tablet-light-docked.png"],
]) {
  const { ctx, page } = await open(viewport)
  await btn(page, "Open AI Chat (fixture launcher)").click()
  await page.waitForSelector("[data-gravitre-float-workspace]")
  const box = await page.locator("[data-gravitre-float-workspace]").boundingBox()
  const inside = box.x >= 0 && box.y >= 0 && box.x + box.width <= viewport.width && box.y + box.height <= viewport.height
  record("responsive", `${label}: window opens inside the viewport`, inside, `mode=${await mode(page)}; box=${Math.round(box.x)},${Math.round(box.y)} ${Math.round(box.width)}×${Math.round(box.height)}`)
  await btn(page, "Dock to side").click()
  await page.waitForSelector('[data-gravitre-wm-placement="docked"]')
  // Measure after the shared-layout transition (MOTION.major = 0.4s) settles.
  await page.waitForTimeout(900)
  const dock = await page.locator('[data-gravitre-wm-placement="docked"]').boundingBox()
  const pad = await page.evaluate(() => getComputedStyle(document.body).paddingRight)
  record("responsive", `${label}: docked width + page reservation`, Math.round(dock.width) === parseInt(pad), `dock width=${Math.round(dock.width)}; body padding-right=${pad}`)
  await shot(page, file)
  const id = await identity(page)
  record("responsive", `${label}: identity kept`, id.instance === "true" && id.messages === "true", JSON.stringify(id))
  await ctx.close()
}

{
  const { ctx, page } = await open({ width: 390, height: 844 }, { seed: { [PREF]: "docked" } })
  // The Vaul sheet is modal (page is aria-hidden while open), so pick the scenario first.
  await scenario(page, "needs approval")
  await btn(page, "Open AI Chat (fixture launcher)").click()
  await page.waitForSelector("[data-gravitre-mobile-sheet-mode]")
  const sheetMode = await page.getAttribute("[data-gravitre-mobile-sheet-mode]", "data-gravitre-mobile-sheet-mode")
  record("responsive", "mobile 390×844: docked preference presents as the float sheet", sheetMode === "float", `sheet mode=${sheetMode}; provider mode=${await mode(page)}`)
  await page.waitForTimeout(900)
  const sheetBox = await page.locator("[data-gravitre-mobile-sheet-mode]").boundingBox()
  const composerBox = await page.locator("[data-gravitre-mobile-sheet-mode] textarea").boundingBox()
  record(
    "responsive",
    "mobile: sheet on-screen and composer reachable at the float snap",
    sheetBox.y < 844 && composerBox && composerBox.y + composerBox.height <= 844,
    `sheet top=${Math.round(sheetBox.y)}; composer=${composerBox ? `${Math.round(composerBox.y)}–${Math.round(composerBox.y + composerBox.height)}` : "missing"} of 844`,
  )
  await page.waitForSelector('[data-gravitre-mobile-sheet-mode] [data-gravitre-ai-runtime-state="needs_approval"]')
  const approveBtn = page.locator("[data-gravitre-mobile-sheet-mode]").getByRole("button", { name: /^approve/i }).first()
  const approveBox = (await approveBtn.count()) ? await approveBtn.boundingBox() : null
  const overlayOpen = await page.locator("[data-gravitre-mobile-sheet-mode]").getByRole("button", { name: "Back to conversation" }).count()
  record(
    "responsive",
    "mobile: needs approval keeps Approve on-screen (no overlay covering it)",
    Boolean(approveBox && approveBox.y >= 0 && approveBox.y + approveBox.height <= 844) && overlayOpen === 0,
    `approve=${approveBox ? `${Math.round(approveBox.y)}–${Math.round(approveBox.y + approveBox.height)}` : "missing"} of 844; work overlay open=${overlayOpen > 0}`,
  )
  await shot(page, "11-mobile-light-sheet.png")
  await btn(page, "Minimize to helper").click()
  await page.waitForSelector("[data-slice1-preview-launcher]")
  await btn(page, "Open AI Chat (fixture launcher)").click()
  await page.waitForSelector("[data-gravitre-mobile-sheet-mode]")
  const id = await identity(page)
  record("responsive", "mobile: minimize and restore recover the same conversation", id.instance === "true" && id.messages === "true", JSON.stringify(id))
  await page.evaluate(() => document.documentElement.classList.add("dark"))
  await page.waitForTimeout(200)
  await shot(page, "12-mobile-dark-sheet.png")
  await ctx.close()
}

// ── Responsive change mid-session keeps the conversation ───────────────────
{
  const { ctx, page } = await open({ width: 1440, height: 900 })
  await btn(page, "Open AI Chat (fixture launcher)").click()
  await page.waitForSelector("[data-gravitre-float-workspace]")
  await page.setViewportSize({ width: 390, height: 844 })
  await page.waitForSelector("[data-gravitre-mobile-sheet-mode]")
  await page.setViewportSize({ width: 1440, height: 900 })
  await page.waitForSelector("[data-gravitre-float-workspace]")
  const id = await identity(page)
  record("responsive", "desktop → mobile → desktop resize keeps conversation and provider", id.instance === "true" && id.messages === "true", `${JSON.stringify(id)}; mode=${await mode(page)}`)
  await ctx.close()
}

await browser.close()
writeFileSync(join(OUT, "slice-1-validation.json"), JSON.stringify({ ranAt: new Date().toISOString(), url: URL, results }, null, 2))
const failed = results.filter((r) => r.result === "FAIL").length
console.log(`\n${results.length - failed}/${results.length} PASS`)
process.exit(failed ? 1 : 0)
