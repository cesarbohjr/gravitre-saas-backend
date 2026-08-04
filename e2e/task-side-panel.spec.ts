import { test, expect } from "@playwright/test"

test.describe("Task side panel (progress UX v2)", () => {
  test("mode=on shows panel at threshold ≥3 with Progress checklist", async ({ page }) => {
    await page.goto("/e2e/task-side-panel?mode=on")
    const harness = page.getByTestId("task-side-panel-harness")
    await expect(harness).toBeVisible()
    await expect(harness).toHaveAttribute("data-show-panel", "true")
    await expect(harness).toHaveAttribute("data-threshold", "3")

    const panel = page.getByTestId("task-side-panel")
    await expect(panel).toBeVisible()
    await expect(panel).toHaveAttribute("data-step-count", "3")
    await expect(panel.getByText("Progress", { exact: true })).toBeVisible()
    await expect(panel.getByText("Outputs", { exact: true })).toBeVisible()
    await expect(panel.getByText("Context", { exact: true })).toBeVisible()
    await expect(panel.getByText(/Create contact list/i).first()).toBeVisible()
    await expect(page.getByTestId("task-side-panel-absent")).toHaveCount(0)

    await page.screenshot({
      path: "docs/delivery/_artifacts/task-side-panel-harness.png",
      fullPage: true,
    })
  })

  test("mode=off keeps inline-only experience under threshold", async ({ page }) => {
    await page.goto("/e2e/task-side-panel?mode=off")
    const harness = page.getByTestId("task-side-panel-harness")
    await expect(harness).toBeVisible()
    await expect(harness).toHaveAttribute("data-show-panel", "false")
    await expect(page.getByTestId("task-side-panel")).toHaveCount(0)
    await expect(page.getByTestId("task-side-panel-absent")).toBeVisible()
  })
})
