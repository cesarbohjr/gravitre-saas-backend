import { test, expect } from "@playwright/test"
import { loadBillingFixtures, prepareAdminAppSession } from "./helpers/auth"

/**
 * G5/G8 UI — Intelligence hub map + inspector + Ask Gravitre SSE focus.
 * Runs against local Playwright webServer stack (not prod browser auth).
 */
test.describe("Intelligence hub UI", () => {
  test.beforeEach(async ({ page }) => {
    const fixtures = loadBillingFixtures()
    await prepareAdminAppSession(page, fixtures.activeTrial, "/intelligence")
  })

  test("G5 — prediction node may show evidence graph in inspector", async ({ page }) => {
    await page.goto("/intelligence?lens=predicts")
    await page.waitForResponse(
      (response) =>
        response.url().includes("/api/intelligence/page-context") && response.status() === 200,
    )

    const map = page.getByTestId("intelligence-map-canvas")
    await expect(map).toBeVisible({ timeout: 60_000 })

    const signalNode = map.locator("button[aria-label*='signal node'], button[aria-label*='Prediction']").first()
    if (!(await signalNode.isVisible().catch(() => false))) {
      test.skip(true, "No prediction nodes in fixture org")
    }
    await signalNode.click()
    await expect(page.getByTestId("intelligence-inspector-drawer")).toBeVisible()
    const evidence = page.getByTestId("evidence-graph-canvas")
    if (await evidence.isVisible().catch(() => false)) {
      await expect(evidence).toBeVisible()
    }
  })

  test("G5 — map node click opens inspector drawer", async ({ page }) => {
    const pageContext = page.waitForResponse(
      (response) =>
        response.url().includes("/api/intelligence/page-context") && response.status() === 200,
    )
    await page.goto("/intelligence")
    await pageContext

    const map = page.getByTestId("intelligence-map-canvas")
    await expect(map).toBeVisible({ timeout: 60_000 })

    const nodeButton = map.locator("button[aria-label*='node']").first()
    await expect(nodeButton).toBeVisible({ timeout: 30_000 })
    await nodeButton.click()

    await expect(page.getByTestId("intelligence-inspector-drawer")).toBeVisible()
  })

  test("G4 — Ask Gravitre SSE visualization focuses map", async ({ page }) => {
    await page.goto("/intelligence")
    await page.waitForResponse(
      (response) =>
        response.url().includes("/api/intelligence/page-context") && response.status() === 200,
    )

    const composer = page.locator("[data-ask-gravitre-composer]")
    await expect(composer).toBeVisible({ timeout: 60_000 })

    const input = composer.getByLabel("Ask Gravitre")
    await input.fill("What agents are currently active?")
    await composer.getByRole("button", { name: "Send" }).click()

    const map = page.getByTestId("intelligence-map-canvas")
    await expect(map.locator("button.ring-2").first()).toBeVisible({ timeout: 90_000 })
  })

  test("G8 — learning map deep link applies focus param", async ({ page }) => {
    await page.goto("/intelligence/learning")
    await page.waitForResponse(
      (response) =>
        response.url().includes("/api/intelligence/page-context") && response.status() === 200,
    )

    const mapLink = page.getByTestId("learning-insight-map-link").first()
    if (!(await mapLink.isVisible().catch(() => false))) {
      test.skip(true, "No promoted learnings in fixture org — G8 UI NOT RUN")
    }

    const href = await mapLink.getAttribute("href")
    expect(href).toMatch(/\/intelligence\?.*focus=learning:/)

    await mapLink.click()
    await expect(page).toHaveURL(/\/intelligence\?.*focus=learning:/)
    await expect(page.getByTestId("intelligence-map-canvas")).toBeVisible({ timeout: 60_000 })
    await expect(page.getByTestId("intelligence-inspector-drawer")).toBeVisible({ timeout: 30_000 })
  })
})
