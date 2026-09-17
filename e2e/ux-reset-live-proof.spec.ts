import { test, expect } from "@playwright/test"
import {
  mockCanonicalChat,
  openHelper,
  readAiDebug,
  waitForRuntime,
  waitForTestApi,
} from "./helpers/canonical-ai"

const SHOTS = "e2e/artifacts/phase-live-proof"

test.describe("UX Reset live proof — morph, voice/tools, AuthGate, agent stream, I11", () => {
  test("compact → expanded morph keeps the shared layout id and one runtime", async ({ page }) => {
    await mockCanonicalChat(page)
    await page.goto("/e2e/shots/home")
    await expect(page.locator("[data-gravitre-ai-helper]")).toBeVisible({ timeout: 60_000 })
    await openHelper(page)
    await waitForRuntime(page)

    const compact = page.locator("[data-gravitre-float-workspace]")
    await expect(compact).toBeVisible()
    const compactLayout = await compact.getAttribute("data-gravitre-workspace-layout-id")
    expect(compactLayout).toBe("gravitre-ai-workspace-frame")
    const instance = (await readAiDebug(page))?.currentInstanceId
    const compactBox = await compact.boundingBox()
    expect(compactBox).toBeTruthy()

    await page.locator("[data-chat-window-control='expand']").click()
    const shell = page.locator("[data-gravitre-ai-shell]")
    await expect(shell).toBeVisible({ timeout: 30_000 })
    await expect.poll(async () => (await readAiDebug(page))?.canonicalPresentation).toBe("expanded")
    expect(await shell.getAttribute("data-gravitre-workspace-layout-id")).toBe(compactLayout)
    const debug = await readAiDebug(page)
    expect(debug?.liveInstanceCount).toBe(1)
    expect(debug?.currentInstanceId).toBe(instance)
    const expandedBox = await shell.boundingBox()
    expect(expandedBox).toBeTruthy()
    if (compactBox && expandedBox) {
      expect(expandedBox.width * expandedBox.height).toBeGreaterThan(compactBox.width * compactBox.height)
    }
    await page.screenshot({ path: `${SHOTS}/morph-expanded.png`, fullPage: true })
  })

  test("voice snapshot and in-flight stream survive compact → expanded", async ({ page }) => {
    await mockCanonicalChat(page, { slowMs: 800, toolThenText: true })
    await page.goto("/e2e/shots/home")
    await expect(page.locator("[data-gravitre-ai-helper]")).toBeVisible({ timeout: 60_000 })
    await openHelper(page)
    await waitForRuntime(page)
    const instance = (await readAiDebug(page))?.currentInstanceId

    await page.evaluate(() => {
      const api = (
        window as Window & {
          __GRAVITRE_AI_TEST?: {
            setVoice: (snapshot: {
              modality: string
              presence: string
              billing: boolean
            }) => void
          }
        }
      ).__GRAVITRE_AI_TEST
      api?.setVoice({ modality: "voice", presence: "listening", billing: false })
    })
    await expect.poll(async () => (await readAiDebug(page))?.voicePresence).toBe("listening")

    const composer = page.getByPlaceholder(/Ask, delegate, or search/i)
    await composer.fill("Search Northwind knowledge.")
    await composer.press("Enter")
    await expect.poll(async () => (await readAiDebug(page))?.streamStatus).toMatch(/submitted|streaming/)

    await page.locator("[data-chat-window-control='expand']").click()
    await expect.poll(async () => (await readAiDebug(page))?.canonicalPresentation).toBe("expanded")
    const after = await readAiDebug(page)
    expect(after?.currentInstanceId).toBe(instance)
    expect(after?.liveInstanceCount).toBe(1)
    // Composer keeps publishing duplex presence. Harness has no mic, so this is
    // idle — the channel is still the same runtime, not a remounted null.
    expect(after?.voicePresence).toBeTruthy()
    await expect(page.getByText("Northwind pipeline looks healthy.")).toBeVisible({ timeout: 30_000 })
  })

  test("AuthGate logout unmounts the canonical runtime without a leftover helper", async ({ page }) => {
    await mockCanonicalChat(page)
    await page.goto("/e2e/shots/home")
    await expect(page.locator("[data-gravitre-ai-helper]")).toBeVisible({ timeout: 60_000 })
    await openHelper(page)
    await waitForRuntime(page)
    expect((await readAiDebug(page))?.liveInstanceCount).toBe(1)

    await page.evaluate(() => {
      const api = (window as Window & { __GRAVITRE_AUTH_TEST?: { clearSession: () => void } })
        .__GRAVITRE_AUTH_TEST
      if (!api?.clearSession) throw new Error("missing __GRAVITRE_AUTH_TEST.clearSession")
      api.clearSession()
    })

    await expect(page.locator("[data-gravitre-ai-helper]")).toHaveCount(0)
    await expect(page.locator("[data-gravitre-float-workspace]")).toHaveCount(0)
    await expect.poll(async () => (await readAiDebug(page))?.liveInstanceCount ?? 0).toBe(0)
  })

  test("fixture agent-chat completes a mocked stream in the same runtime", async ({ page }) => {
    const posts = await mockCanonicalChat(page, { body: "Prioritize overdue HubSpot follow-ups." })
    await page.goto("/e2e/shots/agent-chat")
    await waitForRuntime(page)
    await expect.poll(async () => (await readAiDebug(page))?.agentScopeId).toBe("agt_lead_triage")
    const composer = page.getByPlaceholder(/Ask, delegate, or search/i)
    await composer.fill("What should I prioritize today?")
    await composer.press("Enter")
    await expect.poll(() => posts.length).toBe(1)
    await expect(page.getByText("Prioritize overdue HubSpot follow-ups.")).toBeVisible({ timeout: 30_000 })
    expect((await readAiDebug(page))?.liveInstanceCount).toBe(1)
    await page.screenshot({ path: `${SHOTS}/agent-stream.png`, fullPage: true })
  })

  test("I11 hub is seven text links with no Training item", async ({ page }) => {
    await page.goto("/e2e/shots/intelligence")
    const hub = page.getByRole("navigation", { name: "Intelligence hub" })
    await expect(hub).toBeVisible({ timeout: 60_000 })
    await expect(hub.getByRole("link")).toHaveCount(7)
    await expect(hub.getByRole("link", { name: "Training" })).toHaveCount(0)
    await expect(hub.getByRole("link", { name: "Reports" })).toBeVisible()
    await expect(hub.getByRole("link", { name: "Model Studio" })).toBeVisible()
  })
})
