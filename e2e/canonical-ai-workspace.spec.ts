import { test, expect } from "@playwright/test"
import { mockCanonicalChat, openHelper, readAiDebug, waitForRuntime, waitForTestApi } from "./helpers/canonical-ai"

const SHOTS = "e2e/artifacts/phase-1b"

test.describe("UX Reset 1.0 Phase 1B — canonical AI workspace", () => {
  test.beforeEach(async ({ page }) => {
    await mockCanonicalChat(page)
  })

  test("single runtime survives compact → expanded → fullscreen → compact → minimize → restore", async ({
    page,
  }) => {
    test.setTimeout(240_000)
    await page.goto("/e2e/shots/home")
    await expect(page.locator("[data-gravitre-ai-helper]")).toBeVisible({ timeout: 60_000 })
    await openHelper(page)
    await waitForRuntime(page)

    await expect(page.locator("[data-gravitre-float-workspace]")).toBeVisible({ timeout: 30_000 })
    let debug = await readAiDebug(page)
    expect(debug?.liveInstanceCount).toBe(1)
    expect(debug?.canonicalPresentation).toBe("compact")
    const instanceA = debug?.currentInstanceId
    expect(instanceA).toBeTruthy()
    await page.screenshot({ path: `${SHOTS}/compact.png`, fullPage: true })

    await page.locator("[data-chat-window-control='expand']").click()
    await expect.poll(async () => (await readAiDebug(page))?.canonicalPresentation).toBe("expanded")
    debug = await readAiDebug(page)
    expect(debug?.liveInstanceCount).toBe(1)
    expect(debug?.currentInstanceId).toBe(instanceA)
    await page.screenshot({ path: `${SHOTS}/expanded.png`, fullPage: true })

    await page.locator("[data-chat-window-control='fullscreen']").click()
    await expect.poll(async () => (await readAiDebug(page))?.canonicalPresentation).toBe("fullscreen")
    debug = await readAiDebug(page)
    expect(debug?.liveInstanceCount).toBe(1)
    expect(debug?.currentInstanceId).toBe(instanceA)
    await page.screenshot({ path: `${SHOTS}/fullscreen.png`, fullPage: true })

    await page.locator("[data-chat-window-control='collapseToFloat']").click()
    await expect.poll(async () => (await readAiDebug(page))?.canonicalPresentation).toBe("compact")
    debug = await readAiDebug(page)
    expect(debug?.currentInstanceId).toBe(instanceA)

    await page.locator("[data-chat-window-control='minimizeToHelper']").click()
    await expect.poll(async () => (await readAiDebug(page))?.canonicalPresentation).toBe("minimized")
    await expect(page.locator("[data-gravitre-ai-helper]")).toBeVisible()
    debug = await readAiDebug(page)
    expect(debug?.liveInstanceCount).toBe(1)
    expect(debug?.currentInstanceId).toBe(instanceA)
    await page.screenshot({ path: `${SHOTS}/minimized.png`, fullPage: true })

    await openHelper(page)
    await expect.poll(async () => (await readAiDebug(page))?.liveInstanceCount).toBe(1)
    debug = await readAiDebug(page)
    expect(debug?.currentInstanceId).toBe(instanceA)
    expect(debug?.canonicalPresentation).not.toBe("minimized")
  })

  test("Ask Gravitre opens compact over the current page with no second runtime", async ({ page }) => {
    const posts = await mockCanonicalChat(page)
    await page.goto("/e2e/shots/proof")
    await expect(page.locator("[data-gravitre-proof-page]")).toBeVisible({ timeout: 60_000 })

    await page.locator("[data-select-acme]").click()
    await expect(page.locator("[data-selected-label]")).toContainText("Acme Corporation")

    const composer = page.locator("[data-ask-gravitre-composer]")
    await composer.getByRole("textbox", { name: "Ask Gravitre" }).fill("What changed for Acme?")
    await composer.getByRole("button", { name: "Ask Gravitre" }).click()

    await waitForRuntime(page)
    await expect.poll(async () => (await readAiDebug(page))?.canonicalPresentation).toBe("compact")
    const debug = await readAiDebug(page)
    expect(debug?.liveInstanceCount).toBe(1)
    expect(debug?.selected?.label).toBe("Acme Corporation")
    await expect.poll(() => posts.length).toBeGreaterThanOrEqual(1)
    const contextual = posts.find(
      (item) =>
        (item as { workspace_focus?: { selection?: { object_id?: string } } }).workspace_focus?.selection
          ?.object_id === "acme",
    )
    expect(contextual).toBeTruthy()
    expect((contextual as { research_scope?: string }).research_scope).toBeFalsy()
    await expect(page.locator("[data-gravitre-ai-context]")).toContainText("Acme Corporation")
    await expect(page.locator("[data-gravitre-proof-page]")).toBeVisible()
    await page.screenshot({ path: `${SHOTS}/ask-gravitre-compact.png`, fullPage: true })
  })

  test("selected entity and agent scope do not leak across routes", async ({ page }) => {
    await page.goto("/e2e/shots/proof")
    await expect(page.locator("[data-gravitre-proof-page]")).toBeVisible({ timeout: 60_000 })
    await page.locator("[data-select-acme]").click()
    await page.locator("[data-ask-gravitre-composer]").getByRole("button", { name: "Open Gravitre" }).click()
    await waitForRuntime(page)
    await expect.poll(async () => (await readAiDebug(page))?.selected?.id).toBe("acme")

    await page.evaluate(() => {
      const api = (
        window as Window & {
          __GRAVITRE_AI_TEST?: { setAgentScope: (scope: { agentId: string; name: string } | null) => void }
        }
      ).__GRAVITRE_AI_TEST
      api?.setAgentScope({ agentId: "sales", name: "Sales Agent" })
    })
    await expect.poll(async () => (await readAiDebug(page))?.agentScopeId).toBe("sales")

    await page.goto("/e2e/shots/workflows")
    await page.waitForTimeout(500)
    const after = await readAiDebug(page)
    expect(after?.selected ?? null).toBeNull()
    expect(after?.agentScopeId ?? null).toBeNull()
    if (after?.liveInstanceCount) {
      expect(after.liveInstanceCount).toBe(1)
    }
  })

  test("agent scope summon uses the same runtime instance", async ({ page }) => {
    await page.goto("/e2e/shots/home")
    await expect(page.locator("[data-gravitre-ai-helper]")).toBeVisible({ timeout: 60_000 })
    await openHelper(page)
    await waitForRuntime(page)
    const instance = (await readAiDebug(page))?.currentInstanceId

    await page.evaluate(() => {
      const api = (
        window as Window & {
          __GRAVITRE_AI_TEST?: { summonWorkspace: (opts: Record<string, unknown>) => void }
        }
      ).__GRAVITRE_AI_TEST
      api?.summonWorkspace({
        presentation: "fullscreen",
        agentScope: { agentId: "agent-lead", name: "Lead Enrichment Coordinator" },
      })
    })

    await expect.poll(async () => (await readAiDebug(page))?.canonicalPresentation).toBe("fullscreen")
    const debug = await readAiDebug(page)
    expect(debug?.liveInstanceCount).toBe(1)
    expect(debug?.currentInstanceId).toBe(instance)
    expect(debug?.agentScopeId).toBe("agent-lead")
    await page.screenshot({ path: `${SHOTS}/agent-scoped-fullscreen.png`, fullPage: true })
  })

  test("one submit produces one mocked chat transport POST across compact → expanded", async ({
    page,
  }) => {
    const posts = await mockCanonicalChat(page, { slowMs: 400 })
    await page.goto("/e2e/shots/home")
    await expect(page.locator("[data-gravitre-ai-helper]")).toBeVisible({ timeout: 60_000 })
    await openHelper(page)
    await waitForRuntime(page)

    const composer = page.getByPlaceholder(/Ask, delegate, or search/i)
    await expect(composer).toBeVisible({ timeout: 30_000 })
    await composer.fill("What is the Northwind pipeline?")
    await composer.press("Enter")

    await expect.poll(async () => (await readAiDebug(page))?.chatSubmitCount ?? 0).toBeGreaterThanOrEqual(1)
    await page.locator("[data-chat-window-control='expand']").click()
    await expect.poll(async () => (await readAiDebug(page))?.canonicalPresentation).toBe("expanded")
    await expect.poll(() => posts.length).toBe(1)
    const debug = await readAiDebug(page)
    expect(debug?.liveInstanceCount).toBe(1)
    expect(debug?.chatSubmitCount).toBe(1)
  })

  test("minimize during a mocked stream keeps the same runtime instance", async ({ page }) => {
    await mockCanonicalChat(page, { slowMs: 600 })
    await page.goto("/e2e/shots/home")
    await expect(page.locator("[data-gravitre-ai-helper]")).toBeVisible({ timeout: 60_000 })
    await openHelper(page)
    await waitForRuntime(page)
    const instance = (await readAiDebug(page))?.currentInstanceId

    const composer = page.getByPlaceholder(/Ask, delegate, or search/i)
    await composer.fill("Continue this answer.")
    await composer.press("Enter")
    await page.locator("[data-chat-window-control='minimizeToHelper']").click()
    await expect.poll(async () => (await readAiDebug(page))?.canonicalPresentation).toBe("minimized")
    await openHelper(page)
    const debug = await readAiDebug(page)
    expect(debug?.currentInstanceId).toBe(instance)
    expect(debug?.liveInstanceCount).toBe(1)
  })

  test("refresh on a contextual route does not create two live runtimes", async ({ page }) => {
    await page.goto("/e2e/shots/home")
    await expect(page.locator("[data-gravitre-ai-helper]")).toBeVisible({ timeout: 60_000 })
    await openHelper(page)
    await waitForRuntime(page)
    await page.reload()
    await waitForTestApi(page)
    await page.evaluate(() => {
      const api = (window as Window & { __GRAVITRE_AI_TEST?: { restoreFromHelper: () => void } }).__GRAVITRE_AI_TEST
      api?.restoreFromHelper()
    })
    await waitForRuntime(page)
    expect((await readAiDebug(page))?.liveInstanceCount).toBe(1)
  })

  test("back/forward between shots routes keeps at most one runtime", async ({ page }) => {
    await page.goto("/e2e/shots/proof")
    await expect(page.locator("[data-gravitre-proof-page]")).toBeVisible({ timeout: 60_000 })
    await page.locator("[data-ask-gravitre-composer]").getByRole("button", { name: "Open Gravitre" }).click()
    await waitForRuntime(page)
    const instance = (await readAiDebug(page))?.currentInstanceId
    await page.goto("/e2e/shots/workflows")
    await page.goBack()
    await expect(page.locator("[data-gravitre-proof-page]")).toBeVisible({ timeout: 30_000 })
    await page.goForward()
    await page.waitForTimeout(400)
    const after = await readAiDebug(page)
    if (after?.liveInstanceCount) {
      expect(after.liveInstanceCount).toBe(1)
    }
    void instance
  })

  test("launcher is keyboard focusable and opens the workspace", async ({ page }) => {
    await page.goto("/e2e/shots/home")
    const helper = page.locator("[data-gravitre-ai-helper]")
    await expect(helper).toBeVisible({ timeout: 60_000 })
    await helper.focus()
    await expect(helper).toBeFocused()
    await helper.press("Enter")
    await waitForRuntime(page)
    expect((await readAiDebug(page))?.liveInstanceCount).toBe(1)
    const composer = page.getByPlaceholder(/Ask, delegate, or search/i)
    await expect(composer).toBeVisible()
    await page.keyboard.press("Escape")
    const afterEscape = await readAiDebug(page)
    expect(afterEscape?.liveInstanceCount).toBe(1)
  })

  test("/assistant middleware redirects toward /ai", async ({ request }) => {
    const response = await request.get("/assistant", { maxRedirects: 0 })
    expect(response.status()).toBeGreaterThanOrEqual(300)
    expect(response.status()).toBeLessThan(400)
    const location = response.headers().location || ""
    expect(location).toMatch(/\/ai/)
  })

  test("stale selection is not attached after leaving the page", async ({ page }) => {
    const posts = await mockCanonicalChat(page)
    await page.goto("/e2e/shots/proof")
    await page.locator("[data-select-acme]").click()
    const ask = page.locator("[data-ask-gravitre-composer]")
    await ask.getByRole("textbox", { name: "Ask Gravitre" }).fill("Summarize this customer.")
    await ask.getByRole("button", { name: "Ask Gravitre" }).click()
    await waitForRuntime(page)
    await expect.poll(() => posts.length).toBeGreaterThanOrEqual(1)
    expect(
      (posts[0] as { workspace_focus?: { selection?: { object_id?: string } } }).workspace_focus?.selection
        ?.object_id,
    ).toBe("acme")

    await page.goto("/e2e/shots/workflows")
    await waitForTestApi(page)
    await page.evaluate(() => {
      const api = (window as Window & { __GRAVITRE_AI_TEST?: { restoreFromHelper: () => void } }).__GRAVITRE_AI_TEST
      api?.restoreFromHelper()
    })
    await waitForRuntime(page)
    const composer = page.getByPlaceholder(/Ask, delegate, or search/i)
    await composer.fill("What is slow in our AI pipeline?")
    await composer.press("Enter")
    await expect.poll(() => posts.length).toBeGreaterThanOrEqual(2)
    const later = posts[posts.length - 1] as {
      workspace_focus?: { selection?: { object_id?: string } | null }
    }
    expect(later.workspace_focus?.selection ?? null).toBeNull()
  })

  test("fixture agent-chat route uses the same runtime and sends agent_id", async ({ page }) => {
    const posts = await mockCanonicalChat(page)
    await page.goto("/e2e/shots/agent-chat")
    await waitForRuntime(page)
    await expect.poll(async () => (await readAiDebug(page))?.agentScopeId).toBe("agt_lead_triage")
    await expect.poll(async () => (await readAiDebug(page))?.agentScopeName).toBe("Inbound Lead Triage")
    await expect(page.locator("[data-gravitre-ai-context]")).toContainText("Talking with Inbound Lead Triage")
    expect((await readAiDebug(page))?.liveInstanceCount).toBe(1)
    const composer = page.getByPlaceholder(/Ask, delegate, or search/i)
    await expect(composer).toBeVisible({ timeout: 30_000 })
    await composer.fill("What should I prioritize today?")
    await composer.press("Enter")
    await expect.poll(() => posts.length).toBe(1)
    const body = posts[0] as { agent_id?: string; mode?: string; surface?: string }
    expect(body.agent_id).toBe("agt_lead_triage")
    expect(body.mode).toBe("agent")
    expect(body.surface).toBe("agent_chat")
    expect((await readAiDebug(page))?.liveInstanceCount).toBe(1)
  })

  for (const shot of ["agents", "activity", "workflows", "connectors", "approvals"] as const) {
    test(`header Ask Gravitre on ${shot} summons the same compact runtime`, async ({ page }) => {
      await page.goto(`/e2e/shots/${shot}`)
      await expect(page.locator("[data-ask-gravitre-summon]")).toBeVisible({ timeout: 60_000 })
      await page.locator("[data-ask-gravitre-summon]").first().click()
      await waitForRuntime(page)
      const debug = await readAiDebug(page)
      expect(debug?.liveInstanceCount).toBe(1)
      expect(debug?.canonicalPresentation).toBe("compact")
    })
  }

  test("Agents hub is text links; Connectors default is list rows", async ({ page }) => {
    await page.goto("/e2e/shots/agents")
    await expect(page.getByRole("navigation", { name: "Agents hub" })).toBeVisible({ timeout: 60_000 })
    await expect(page.getByRole("navigation", { name: "Agents hub" }).getByRole("link", { name: "Roster" })).toBeVisible()

    await page.goto("/e2e/shots/connectors")
    await expect(page.locator("[data-gravitre-connector-row]").first()).toBeVisible({ timeout: 60_000 })
  })

  test("marketing home does not mount the authenticated canonical runtime", async ({ page }) => {
    await page.goto("/")
    const debug = await readAiDebug(page)
    expect(debug?.liveInstanceCount ?? 0).toBe(0)
    await expect(page.locator("[data-gravitre-ai-helper]")).toHaveCount(0)
  })

  test("shots /ai query params apply on the harness /ai path", async ({ page }) => {
    const posts = await mockCanonicalChat(page)
    await page.goto("/e2e/shots/ai?prompt=hello-from-query&mode=chat")
    await waitForRuntime(page)
    const composer = page.getByPlaceholder(/Ask, delegate, or search/i)
    await expect(composer).toBeVisible({ timeout: 60_000 })
    await expect.poll(async () => (await readAiDebug(page))?.canonicalPresentation).toBe("fullscreen")
    await expect.poll(() => posts.length).toBeGreaterThanOrEqual(1)
    expect((await readAiDebug(page))?.liveInstanceCount).toBe(1)
  })

  for (const width of [390, 430, 768, 1024, 1280, 1440, 1728]) {
    test(`responsive workspace at ${width}px keeps an entry point`, async ({ page }) => {
      await page.setViewportSize({ width, height: 900 })
      await page.goto("/e2e/shots/home")
      const helper = page.locator("[data-gravitre-ai-helper]")
      await expect(helper).toBeVisible({ timeout: 60_000 })
      const box = await helper.boundingBox()
      expect(box).toBeTruthy()
      if (box) {
        expect(box.x + box.width).toBeLessThanOrEqual(width + 8)
        expect(box.y + box.height).toBeLessThanOrEqual(900 + 8)
      }
      await helper.click()
      await waitForRuntime(page)
      expect((await readAiDebug(page))?.liveInstanceCount).toBe(1)
      await page.screenshot({ path: `${SHOTS}/responsive-${width}.png` })
    })
  }
})
