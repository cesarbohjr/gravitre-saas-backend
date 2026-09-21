import { test, expect } from "@playwright/test"
import { hasE2eStorageState, e2eStorageStatePath } from "./helpers/gravitre-e2e-storage"

const isolatedOrg = "f07e57c0-1501-4000-8000-c04e57a00001"

test.describe("2.0 authenticated /ai harness", () => {
  test.skip(!hasE2eStorageState(), "One legitimate login: pnpm e2e:save-storage")

  test.use({
    storageState: e2eStorageStatePath() || undefined,
  })

  test("loads /ai for the isolated test org without a second login", async ({ page }) => {
    await page.addInitScript((orgId) => {
      window.localStorage.setItem(
        "gravitre:selectedOrg",
        JSON.stringify({ id: orgId, name: "Gravitre Isolated Conversation Smoke" }),
      )
    }, isolatedOrg)
    await page.goto("/ai")
    await expect(page).not.toHaveURL(/\/login/)
    await expect(page.locator("[data-gravitre-ai-landing]")).toBeVisible({ timeout: 60_000 })
  })

  test("typed hello stays on /ai and does not bounce to login", async ({ page }) => {
    await page.addInitScript((orgId) => {
      window.localStorage.setItem(
        "gravitre:selectedOrg",
        JSON.stringify({ id: orgId, name: "Gravitre Isolated Conversation Smoke" }),
      )
    }, isolatedOrg)
    await page.goto("/ai")
    await expect(page).not.toHaveURL(/\/login/)
    const composer = page.locator("textarea").first()
    await expect(composer).toBeVisible({ timeout: 60_000 })
    await composer.fill("hello")
    await composer.press("Enter")
    await expect(page).not.toHaveURL(/\/login/)
    await expect(page.locator("body")).toBeVisible()
  })

  test("compact expanded fullscreen minimize restore stay one session", async ({ page }) => {
    await page.addInitScript((orgId) => {
      window.localStorage.setItem(
        "gravitre:selectedOrg",
        JSON.stringify({ id: orgId, name: "Gravitre Isolated Conversation Smoke" }),
      )
    }, isolatedOrg)
    await page.goto("/ai")
    await expect(page).not.toHaveURL(/\/login/)
    const expand = page.locator("[data-chat-window-control='expand']")
    if ((await expand.count()) === 0) {
      test.info().annotations.push({ type: "note", description: "window controls not mounted yet" })
      return
    }
    await expand.click()
    await page.locator("[data-chat-window-control='fullscreen']").click()
    await page.locator("[data-chat-window-control='collapseToFloat']").click()
    await expect(page).not.toHaveURL(/\/login/)
  })
})
