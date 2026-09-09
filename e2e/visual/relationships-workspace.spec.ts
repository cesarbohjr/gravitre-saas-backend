/**
 * Relationships graph workspace — smoke + interaction (fixture harness only).
 */
import { test, expect } from "@playwright/test"

test.describe("Relationships graph workspace", () => {
  test.beforeEach(async ({ page }) => {
    await page.emulateMedia({ reducedMotion: "reduce" })
  })

  test("loads graph-first workspace with metrics and toggles", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 })
    await page.goto("/e2e/shots/relationships", { waitUntil: "networkidle" })

    await expect(page.getByRole("heading", { name: "Organization knowledge graph" })).toBeVisible()
    await expect(page.getByText("Organization knowledge", { exact: true }).first()).toBeVisible()
    await expect(page.getByText("Learned relationships", { exact: true }).first()).toBeVisible()
    await expect(page.getByRole("group", { name: "View mode" })).toBeVisible()
    await expect(page.locator(".react-flow")).toBeVisible({ timeout: 15_000 })
  })

  test("table view preserves parity controls", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 })
    await page.goto("/e2e/shots/relationships", { waitUntil: "networkidle" })

    await page.getByRole("radio", { name: "Table" }).click()
    await expect(page.getByRole("columnheader", { name: "From" })).toBeVisible()
    await expect(page.getByRole("columnheader", { name: "Link" })).toBeVisible()
    await expect(page.getByRole("columnheader", { name: "To" })).toBeVisible()
    await expect(page.getByText("Northwind Logistics").first()).toBeVisible()
  })

  test("add knowledge drawer opens from toolbar", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 })
    await page.goto("/e2e/shots/relationships", { waitUntil: "networkidle" })

    await page.getByRole("button", { name: "Add knowledge" }).click()
    await expect(page.getByRole("heading", { name: "Add organization knowledge" })).toBeVisible()
  })
})
