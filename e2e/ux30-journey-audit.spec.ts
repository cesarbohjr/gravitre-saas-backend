import { existsSync } from "node:fs"
import path from "node:path"
import { test, expect } from "@playwright/test"
import { loadBillingFixtures, prepareAdminAppSession, waitForAppShellReady } from "./helpers/auth"

const fixturesPath = path.resolve(__dirname, ".fixtures", "billing-users.json")

const appOrigin = process.env.PLAYWRIGHT_BASE_URL ?? "http://localhost:3001"

/** Staging / live auth requires real Supabase — never placeholder test host. */
function hasLiveAuthEnv(): boolean {
  const url = process.env.SUPABASE_URL ?? process.env.NEXT_PUBLIC_SUPABASE_URL ?? ""
  return Boolean(url) && !url.includes("test.supabase.co") && !url.includes("placeholder")
}

const skipLiveJourneys =
  process.env.PLAYWRIGHT_SKIP_BACKEND === "1" ||
  !existsSync(fixturesPath) ||
  !hasLiveAuthEnv()

function isStagingTarget(): boolean {
  try {
    const host = new URL(appOrigin).hostname
    return host !== "localhost" && host !== "127.0.0.1"
  } catch {
    return false
  }
}

test.describe("UX/UI 3.0 Plus — authenticated journey audit (staging first)", () => {
  test.beforeEach(async ({ page }) => {
    test.skip(skipLiveJourneys, "Requires billing fixtures, FastAPI, and live Supabase credentials")
    test.setTimeout(600_000)
    const user = loadBillingFixtures().activeTrial
    await prepareAdminAppSession(page, user, "/home")
    await waitForAppShellReady(page)
  })

  test("J1 — Login → Home dashboard and nav", async ({ page }) => {
    await expect(page).toHaveURL(/\/home/)
    await expect(page.locator("aside nav")).toBeVisible()
    await expect(page.getByRole("heading", { name: /home/i }).first()).toBeVisible({ timeout: 60_000 })
    test.info().annotations.push({
      type: "journey",
      description: `PASS — J1 @ ${new Date().toISOString()} target=${appOrigin}`,
    })
  })

  test("J6 — Intelligence lens switch (Knows → Learns → Predicts)", async ({ page }) => {
    const pageContext = page.waitForResponse(
      (response) =>
        response.url().includes("/api/intelligence/page-context") && response.status() === 200,
    )
    await page.goto("/intelligence")
    await pageContext

    const map = page.getByTestId("intelligence-map-canvas")
    await expect(map).toBeVisible({ timeout: 90_000 })

    const lensBar = page.getByRole("tablist", { name: "Intelligence map lenses" })
    await expect(lensBar).toBeVisible()

    for (const label of ["Learns", "Predicts"] as const) {
      await lensBar.getByRole("tab", { name: label }).click()
      await expect(lensBar.getByRole("tab", { name: label, selected: true })).toBeVisible()
      await expect(map).toBeVisible()
    }

    test.info().annotations.push({
      type: "journey",
      description: `PASS — J6 lens switch @ ${new Date().toISOString()} target=${appOrigin}`,
    })
  })

  test("J7 — Activity failure inspect and trace link", async ({ page }) => {
    await page.goto("/activity")
    await expect(page.getByRole("heading", { name: "Activity" })).toBeVisible({ timeout: 60_000 })

    await page.waitForResponse(
      (response) => response.url().includes("/api/business-outcomes") && response.status() === 200,
      { timeout: 60_000 },
    ).catch(() => undefined)

    const statusTrigger = page.getByRole("combobox").filter({ hasText: /Status|All/i }).first()
    if (await statusTrigger.isVisible().catch(() => false)) {
      await statusTrigger.click()
      await page.getByRole("option", { name: "Failed" }).click()
    }

    const outcomeRow = page.locator('[role="option"]').first()
    if (!(await outcomeRow.isVisible().catch(() => false))) {
      test.skip(true, "BLOCKED — no business outcomes in fixture org (try failed filter)")
    }
    await outcomeRow.click()

    const traceLink = page.locator('a[href*="/runs/"][href*="trace=1"]').first()
    const runLink = page.locator('a[href*="/runs/"]').first()
    if (await traceLink.isVisible().catch(() => false)) {
      await expect(traceLink).toBeVisible()
    } else if (await runLink.isVisible().catch(() => false)) {
      await expect(runLink).toBeVisible()
    } else {
      test.skip(true, "BLOCKED — outcome selected but no run/trace link in fixture org")
    }

    test.info().annotations.push({
      type: "journey",
      description: `PASS — J7 activity failure inspect @ ${new Date().toISOString()} target=${appOrigin}`,
    })
  })

  test("J11 — Command palette navigates to Activity without sidebar", async ({ page }) => {
    await page.goto("/home")
    await waitForAppShellReady(page)

    await page.keyboard.press("Control+K")
    const dialog = page.getByRole("dialog")
    await expect(dialog).toBeVisible({ timeout: 15_000 })

    const input = dialog.getByPlaceholder(/command or search/i)
    await input.fill("Runs")
    await dialog.getByRole("option", { name: /Runs/i }).click()

    await expect(page).toHaveURL(/\/activity/, { timeout: 30_000 })
    await expect(page.getByRole("heading", { name: "Activity" })).toBeVisible()

    test.info().annotations.push({
      type: "journey",
      description: `PASS — J11 command palette → Activity @ ${new Date().toISOString()} target=${appOrigin}`,
    })
  })
})

test.describe("UX/UI 3.0 Plus — journey environment gate", () => {
  test("documents staging requirement when live auth is unavailable", async () => {
    if (!skipLiveJourneys && isStagingTarget()) {
      test.info().annotations.push({
        type: "journey",
        description: `READY — live auth + staging target ${appOrigin}`,
      })
      return
    }
    test.info().annotations.push({
      type: "journey",
      description: skipLiveJourneys
        ? "BLOCKED — missing fixtures or Supabase credentials (run against staging with secrets)"
        : `NOT PROVEN — local target ${appOrigin}; repeat on staging before prod smoke`,
    })
  })
})
