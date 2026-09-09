/**
 * Agent knowledge — atomic assign/remove + no legacy save bar (fixture harness).
 */
import { test, expect } from "@playwright/test"

test.describe("Agent knowledge workspace", () => {
  test.beforeEach(async ({ page }) => {
    await page.emulateMedia({ reducedMotion: "reduce" })
  })

  test("renders expert packs without legacy save knowledge packs control", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 })
    await page.goto("/e2e/shots/agent-knowledge", { waitUntil: "networkidle" })

    await expect(page.getByTestId("agent-knowledge-shot")).toBeVisible()
    await expect(page.getByRole("heading", { name: "Inbound Lead Triage" })).toBeVisible()
    await expect(page.getByText("Save knowledge packs")).toHaveCount(0)
    await expect(page.getByText("RevOps Playbook")).toBeVisible()
  })

  test("assigns an expert pack from the catalog", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 })
    await page.goto("/e2e/shots/agent-knowledge", { waitUntil: "networkidle" })

    const supportCard = page.locator("article").filter({ hasText: "Support Macros" })
    await supportCard.getByRole("button", { name: "+ Assign" }).click()
    await expect(supportCard.getByText("Assigned")).toBeVisible()
  })

  test("removes an assigned pack without deleting the knowledge base", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 })
    await page.goto("/e2e/shots/agent-knowledge", { waitUntil: "networkidle" })

    const assignedCard = page.locator("article").filter({ hasText: "RevOps Playbook" }).first()
    await expect(assignedCard.getByText("Assigned")).toBeVisible()
    await assignedCard.getByRole("button", { name: "More actions" }).click()
    await page.getByRole("menuitem", { name: "Remove from agent" }).click()
    await expect(assignedCard.getByText("Assigned")).toHaveCount(0)
    await expect(assignedCard.getByRole("button", { name: "+ Assign" })).toBeVisible()
  })

  test("sources tab shows ingestion progress for syncing source", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 })
    await page.goto("/e2e/shots/agent-knowledge", { waitUntil: "networkidle" })

    await page.getByRole("button", { name: "Sources" }).click()
    await expect(page.getByText("Pricing enablement deck")).toBeVisible()
    await expect(page.getByText("Indexing")).toBeVisible()
    await expect(page.getByText("Creating searchable knowledge…")).toBeVisible()
  })
})
