/**
 * Relationships graph workspace — prod parity checklist (fixture harness).
 * Exercises the same UI components mounted on /intelligence/learning → Relationships.
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

  test("metric strip reflects fixture counts", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 })
    await page.goto("/e2e/shots/relationships", { waitUntil: "networkidle" })

    await expect(page.getByText("2", { exact: true }).first()).toBeVisible()
    await expect(page.getByText("3", { exact: true }).first()).toBeVisible()
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

  test("inspector opens on table row and Ask Gravitre AI link is prefilled", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 })
    await page.goto("/e2e/shots/relationships", { waitUntil: "networkidle" })

    await page.getByRole("radio", { name: "Table" }).click()
    await page.locator("tbody tr").filter({ hasText: "RevOps playbook" }).first().click()
    const aside = page.locator("aside")
    await expect(aside.getByText("Learned relationship").first()).toBeVisible()
    const askLink = aside.locator('a[href*="/ai?prompt="]')
    await expect(askLink).toBeVisible()
  })

  test("archive control visible on relationship row", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 })
    await page.goto("/e2e/shots/relationships", { waitUntil: "networkidle" })

    await page.getByRole("radio", { name: "Table" }).click()
    await expect(page.getByRole("button", { name: "Archive" }).first()).toBeVisible()
  })

  test("add knowledge drawer opens from toolbar", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 })
    await page.goto("/e2e/shots/relationships", { waitUntil: "networkidle" })

    await page.getByRole("button", { name: "Add entity" }).click()
    await expect(page.getByRole("heading", { name: "Add organization entity" })).toBeVisible()
  })

  test("mobile layout opens inspector sheet on selection", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 })
    await page.goto("/e2e/shots/relationships", { waitUntil: "networkidle" })

    await page.getByRole("radio", { name: "Table" }).click()
    await page.getByText("RevOps playbook").first().click()
    await expect(page.getByRole("dialog")).toBeVisible()
    await expect(page.getByText("Learned relationship").first()).toBeVisible()
  })

  test("seeded node edit control in graph inspector", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 })
    await page.goto("/e2e/shots/relationships", { waitUntil: "networkidle" })
    await expect(page.locator(".react-flow")).toBeVisible({ timeout: 15_000 })

    const seededNode = page
      .locator(".react-flow__node")
      .filter({ hasText: "Northwind Logistics" })
      .filter({ hasText: "Confirmed knowledge" })
    await expect(seededNode).toBeVisible()
    await seededNode.click()

    const aside = page.locator("aside")
    await expect(aside.getByText("Confirmed organization knowledge").first()).toBeVisible({ timeout: 10_000 })
    await expect(aside.getByTestId("seeded-node-edit")).toBeVisible()
  })
})
