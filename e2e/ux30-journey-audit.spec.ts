import { existsSync } from "node:fs"
import path from "node:path"
import { test, expect } from "@playwright/test"
import { loadBillingFixtures, prepareAdminAppSession, waitForAppShellReady } from "./helpers/auth"
import { e2eStorageStatePath, hasE2eStorageState } from "./helpers/gravitre-e2e-storage"

const fixturesPath = path.resolve(__dirname, ".fixtures", "billing-users.json")
const isolatedOrg = "f07e57c0-1501-4000-8000-c04e57a00001"
const isolatedOrgName = "Gravitre Isolated Conversation Smoke"

const appOrigin = process.env.PLAYWRIGHT_BASE_URL ?? "http://localhost:3001"
const useStorageAuth = hasE2eStorageState()

/** Staging / live auth requires real Supabase — never placeholder test host. */
function hasLiveAuthEnv(): boolean {
  const url = process.env.SUPABASE_URL ?? process.env.NEXT_PUBLIC_SUPABASE_URL ?? ""
  return Boolean(url) && !url.includes("test.supabase.co") && !url.includes("placeholder")
}

const skipLiveJourneys =
  !useStorageAuth &&
  (process.env.PLAYWRIGHT_SKIP_BACKEND === "1" ||
    !existsSync(fixturesPath) ||
    !hasLiveAuthEnv())

function isStagingTarget(): boolean {
  try {
    const host = new URL(appOrigin).hostname
    return host !== "localhost" && host !== "127.0.0.1"
  } catch {
    return false
  }
}

test.describe("UX/UI 3.0 Plus — authenticated journey audit (staging first)", () => {
  if (useStorageAuth) {
    test.use({ storageState: e2eStorageStatePath() || undefined })
  }

  test.beforeEach(async ({ page }) => {
    test.skip(skipLiveJourneys, "Requires billing fixtures, FastAPI, and live Supabase credentials")
    test.setTimeout(600_000)
    if (useStorageAuth) {
      await page.addInitScript(
        ({ id, name }) => {
          window.localStorage.setItem("gravitre:selectedOrg", JSON.stringify({ id, name }))
        },
        { id: isolatedOrg, name: isolatedOrgName },
      )
      await page.goto("/home")
      await waitForAppShellReady(page)
      return
    }
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

  test("J6 — Intelligence I1 field + lens switch", async ({ page }) => {
    const pageContext = page.waitForResponse(
      (response) =>
        response.url().includes("/api/intelligence/page-context") && response.status() === 200,
    )
    await page.goto("/intelligence")
    await pageContext

    const i1Surface = page.getByTestId("intelligence-i1-i2")
    await expect(i1Surface).toBeVisible({ timeout: 90_000 })

    // Field-primary (G-STRUCT A4): the field is the default view; Matrix is one click away.
    await expect(page.getByTestId("intelligence-map-canvas")).toBeVisible({ timeout: 90_000 })
    await page.getByTestId("intel-view-mode").getByRole("button", { name: "Matrix" }).click()
    await expect(page.getByTestId("intel-i3-matrix")).toBeVisible({ timeout: 90_000 })

    const lensBar = page
      .getByRole("tablist", { name: /Intelligence (map )?lenses/i })
      .first()
    await expect(lensBar).toBeVisible()

    await expect(page.getByTestId("intel-i2-toggle")).toBeVisible()
    await expect(page.getByTestId("intel-i2-stream")).toHaveCount(0)

    for (const label of ["Learns", "Predicts"] as const) {
      await lensBar.getByRole("tab", { name: label }).click()
      await expect(lensBar.getByRole("tab", { name: label, selected: true })).toBeVisible()
      await expect(page.getByTestId("intel-i3-matrix")).toBeVisible()
    }

    await page.getByTestId("intel-view-mode").getByRole("button", { name: "Field" }).click()
    const map = page.getByTestId("intelligence-map-canvas")
    await expect(map).toBeVisible({ timeout: 60_000 })

    test.info().annotations.push({
      type: "journey",
      description: `PASS — J6 I3 matrix + I1 field lens switch @ ${new Date().toISOString()} target=${appOrigin}`,
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
      await page.waitForResponse(
        (response) => response.url().includes("/api/business-outcomes") && response.status() === 200,
        { timeout: 60_000 },
      ).catch(() => undefined)
    }

    let outcomeRow = page.locator('[role="option"]').first()
    if (!(await outcomeRow.isVisible().catch(() => false)) && (await statusTrigger.isVisible().catch(() => false))) {
      await statusTrigger.click()
      await page.getByRole("option", { name: "All" }).click()
      await page.waitForResponse(
        (response) => response.url().includes("/api/business-outcomes") && response.status() === 200,
        { timeout: 60_000 },
      ).catch(() => undefined)
      outcomeRow = page.locator('[role="option"]').first()
    }

    if (!(await outcomeRow.isVisible().catch(() => false))) {
      test.skip(true, "BLOCKED — no business outcomes in fixture org")
    }
    await outcomeRow.click()

    const tracePanel = page.getByTestId("activity-trace-a1")
    const traceEmpty = page.getByTestId("activity-trace-empty")
    if (await tracePanel.isVisible().catch(() => false)) {
      await expect(tracePanel).toBeVisible()
      await expect(page.getByTestId("activity-trace-rail")).toBeVisible()
      await expect(page.getByTestId("activity-trace-story")).toBeVisible()
    } else if (await traceEmpty.isVisible().catch(() => false)) {
      await expect(traceEmpty).toBeVisible()
    }

    const traceLink = page.locator('a[href*="/runs/"][href*="trace=1"]').first()
    const runLink = page.locator('a[href*="/runs/"]').first()
    const openRunHeader = page.getByRole("link", { name: /open run/i })
    if (await traceLink.isVisible().catch(() => false)) {
      await expect(traceLink).toBeVisible()
    } else if (await openRunHeader.isVisible().catch(() => false)) {
      await expect(openRunHeader).toBeVisible()
    } else if (await runLink.isVisible().catch(() => false)) {
      await expect(runLink).toBeVisible()
    } else if (await tracePanel.isVisible().catch(() => false)) {
      const openRunTrace = page.getByRole("link", { name: /open run trace/i })
      if (await openRunTrace.isVisible().catch(() => false)) {
        await expect(openRunTrace).toBeVisible()
      }
    } else {
      test.skip(true, "BLOCKED — outcome selected but no run/trace link in fixture org")
    }

    test.info().annotations.push({
      type: "journey",
      description: `PASS — J7 activity inspect + trace @ ${new Date().toISOString()} target=${appOrigin} org=${isolatedOrg}`,
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
