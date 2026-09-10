/**
 * Agents 4.0 — visual goldens + acceptance (Phase 6).
 *
 * Prototypes: `/e2e/shots/agents-4?p=…`
 * Production fleet: `/e2e/shots/agents`
 *
 * Refresh baselines after accepted visual change:
 *   PLAYWRIGHT_REUSE_SERVER=1 pnpm exec playwright test -c playwright.visual.config.ts e2e/visual/agents-4.spec.ts --update-snapshots
 *
 * Do not invent product claims in fixtures.
 */
import { test, expect } from "@playwright/test"

const PROTOTYPE_SHOTS = [
  { id: "1", name: "identity", path: "/e2e/shots/agents-4?p=1" },
  { id: "3", name: "team-grouped", path: "/e2e/shots/agents-4?p=3" },
  { id: "4", name: "list", path: "/e2e/shots/agents-4?p=4" },
  { id: "5", name: "graph", path: "/e2e/shots/agents-4?p=5" },
  { id: "7", name: "inspector", path: "/e2e/shots/agents-4?p=7" },
  { id: "8", name: "picker", path: "/e2e/shots/agents-4?p=8" },
  { id: "11", name: "compare", path: "/e2e/shots/agents-4?p=11" },
] as const

test.describe("Agents 4.0 prototype goldens", () => {
  test.beforeEach(async ({ page }) => {
    await page.emulateMedia({ reducedMotion: "reduce" })
  })

  for (const shot of PROTOTYPE_SHOTS) {
    test(`prototype ${shot.id} ${shot.name} @ desktop-1440`, async ({ page }) => {
      await page.setViewportSize({ width: 1440, height: 900 })
      await page.goto(shot.path, { waitUntil: "domcontentloaded" })
      await page.waitForTimeout(600)
      await expect(page).toHaveScreenshot(`agents-4-${shot.name}-desktop-1440.png`, {
        animations: "disabled",
        caret: "hide",
        // Graph SVG antialiasing / edge layout can drift slightly across runs.
        maxDiffPixelRatio: shot.name === "graph" ? 0.04 : 0.02,
      })
    })
  }

  test("prototype mobile list @ mobile-390", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 })
    await page.goto("/e2e/shots/agents-4?p=10", { waitUntil: "domcontentloaded" })
    await page.waitForTimeout(600)
    await expect(page).toHaveScreenshot("agents-4-mobile-list-mobile-390.png", {
      animations: "disabled",
      caret: "hide",
      maxDiffPixelRatio: 0.02,
    })
  })
})

test.describe("Agents 4.0 production fleet acceptance", () => {
  test.beforeEach(async ({ page }) => {
    await page.emulateMedia({ reducedMotion: "reduce" })
  })

  test("fleet view switcher TEAM / LIST / GRAPH is present", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 })
    await page.goto("/e2e/shots/agents", { waitUntil: "domcontentloaded" })

    const fleetView = page.getByRole("group", { name: "Fleet view" })
    await expect(fleetView).toBeVisible({ timeout: 20_000 })
    await expect(fleetView.getByRole("button", { name: "Team" })).toBeVisible()
    await expect(fleetView.getByRole("button", { name: "List" })).toBeVisible()
    await expect(fleetView.getByRole("button", { name: "Graph" })).toBeVisible()
  })

  test("LIST view renders dense table", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 })
    await page.goto("/e2e/shots/agents?view=list", { waitUntil: "domcontentloaded" })

    await expect(page.getByRole("group", { name: "Fleet view" })).toBeVisible({ timeout: 20_000 })
    await expect(page.getByRole("columnheader", { name: "Agent" })).toBeVisible({
      timeout: 15_000,
    })
  })

  test("GRAPH view shows honest-edge legend copy", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 })
    await page.goto("/e2e/shots/agents?view=graph", { waitUntil: "domcontentloaded" })

    await expect(page.getByRole("group", { name: "Fleet view" })).toBeVisible({ timeout: 20_000 })
    await expect(page.getByText("parent / swarm", { exact: false })).toBeVisible({
      timeout: 15_000,
    })
    await expect(page.getByText("uses connector", { exact: false })).toBeVisible()
  })

  test("production fleet @ desktop-1440 golden", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 })
    await page.goto("/e2e/shots/agents?view=team", { waitUntil: "domcontentloaded" })
    await expect(page.getByRole("group", { name: "Fleet view" })).toBeVisible({ timeout: 20_000 })
    await page.waitForTimeout(500)
    await expect(page).toHaveScreenshot("agents-fleet-team-desktop-1440.png", {
      animations: "disabled",
      caret: "hide",
      maxDiffPixelRatio: 0.02,
    })
  })
})
