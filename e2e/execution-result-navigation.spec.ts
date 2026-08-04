import { test, expect } from "@playwright/test"

test.describe("ExecutionResult navigation buttons", () => {
  test("View in Apollo opens external artifact URL (not connector settings)", async ({ page, context }) => {
    await page.goto("/e2e/execution-result?scenario=apollo_external")
    await expect(page.getByTestId("execution-result-harness")).toBeVisible()

    const viewButton = page.getByRole("link", { name: "View in Apollo" })
    await expect(viewButton).toBeVisible()
    await expect(viewButton).toHaveAttribute("href", /app\.apollo\.io/)

    const [popup] = await Promise.all([
      context.waitForEvent("page"),
      viewButton.click(),
    ])
    await popup.waitForLoadState("domcontentloaded")
    expect(popup.url()).toContain("apollo.io")
    await popup.close()
  })

  test("internal result_url navigates in-app via client routing", async ({ page }) => {
    await page.goto("/e2e/execution-result?scenario=internal_doc")
    const viewButton = page.getByRole("link", { name: "View in Gravitre" })
    await expect(viewButton).toBeVisible()
    await expect(viewButton).toHaveAttribute("href", "/docs/guides/how-to/agents")

    const before = page.url()
    await viewButton.click()
    await page.waitForURL("**/docs/guides/how-to/agents")
    expect(page.url()).not.toBe(before)
    await expect(page.getByRole("main").last()).toContainText(/agent/i)
  })

  test("inline-only success does not show misleading View in Gravitre connector link", async ({ page }) => {
    await page.goto("/e2e/execution-result?scenario=inline_only")
    await expect(page.getByText('Created contact list "Inline summary only".')).toBeVisible()
    await expect(page.getByRole("link", { name: /View in/i })).toHaveCount(0)
  })

  test("hosted_files scenario renders Phase 2 file-reference chips", async ({ page }) => {
    await page.goto("/e2e/execution-result?scenario=hosted_files")
    await expect(page.getByTestId("execution-result-harness")).toBeVisible()
    await expect(page.getByTestId("file-reference-chip").first()).toBeVisible()
    await expect(page.getByText("q3-ops-brief.md")).toBeVisible()
    await expect(page.getByText("q3-ops-brief.docx")).toBeVisible()
    await expect(page.getByTestId("preview-code-pane")).toBeVisible()
  })

  test("preview_code scenario renders Phase 3 Preview/Code pane", async ({ page }) => {
    await page.goto("/e2e/execution-result?scenario=preview_code")
    await expect(page.getByTestId("execution-result-harness")).toBeVisible()
    await expect(page.getByTestId("preview-code-pane")).toBeVisible()
    await expect(page.getByTestId("preview-code-iframe")).toBeVisible()
    await page.getByRole("button", { name: "Code" }).click()
    await expect(page.getByTestId("preview-code-source")).toContainText("statusBreakdown")
  })

  test("business_outcome scenario renders shared evidence card (matched preview)", async ({ page }) => {
    await page.goto("/e2e/execution-result?scenario=business_outcome")
    await expect(page.getByTestId("execution-result-harness")).toBeVisible()
    const card = page.locator('[data-projection="business_outcome"]')
    await expect(card).toBeVisible()
    await expect(card).toHaveAttribute("data-business-outcome-id", "run-bo-fixture")
    await expect(page.getByText(/Created contact list "MSP Prospects" in Apollo/i)).toBeVisible()
    await expect(card.getByText(/^Verified ·/)).toBeVisible()
    const vendor = page.getByRole("link", { name: "View in Apollo" })
    await expect(vendor).toBeVisible()
    await expect(vendor).toHaveAttribute("href", /app\.apollo\.io/)
    await page.screenshot({
      path: "docs/delivery/_artifacts/bo-chat-harness-business-outcome.png",
      fullPage: true,
    })
  })
})
