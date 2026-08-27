import { test, expect } from "@playwright/test"

const AI_COMPOSER_BUDGET_MS = 8_000

test.describe("/ai load and chat history", () => {
  test("shot harness composer is interactive within budget", async ({ page }) => {
    await page.goto("/e2e/shots/ai")

    const started = Date.now()
    await expect(page.getByPlaceholder(/Ask, delegate, or search/i)).toBeVisible({
      timeout: AI_COMPOSER_BUDGET_MS,
    })
    const elapsed = Date.now() - started
    expect(elapsed).toBeLessThan(AI_COMPOSER_BUDGET_MS)
  })
})
