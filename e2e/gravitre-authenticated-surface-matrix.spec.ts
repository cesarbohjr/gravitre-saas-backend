/**
 * Authenticated product-surface matrix against gravitre-e2e-storage.json.
 * Visits Intelligence / Activity / Navigation + Phase-5 surfaces; records
 * PASS only when the route loads without a login bounce and a surface marker
 * is visible. Does not invent product claims.
 */
import { test, expect, type Page } from "@playwright/test"
import { hasE2eStorageState, e2eStorageStatePath } from "./helpers/gravitre-e2e-storage"

const isolatedOrg = "f07e57c0-1501-4000-8000-c04e57a00001"
const orgLabel = "Gravitre Isolated Conversation Smoke"

async function seedOrg(page: Page) {
  await page.addInitScript(
    ({ id, name }) => {
      window.localStorage.setItem("gravitre:selectedOrg", JSON.stringify({ id, name }))
    },
    { id: isolatedOrg, name: orgLabel },
  )
}

async function assertAuthenticatedRoute(
  page: Page,
  path: string,
  marker: () => ReturnType<Page["locator"]>,
) {
  await page.goto(path)
  await expect(page).not.toHaveURL(/\/login/, { timeout: 30_000 })
  await expect(marker()).toBeVisible({ timeout: 90_000 })
}

test.describe("Authenticated product surface matrix", () => {
  test.skip(!hasE2eStorageState(), "Requires e2e/.fixtures/gravitre-e2e-storage.json")
  test.use({ storageState: e2eStorageStatePath() || undefined })
  test.setTimeout(180_000)

  test.beforeEach(async ({ page }) => {
    await seedOrg(page)
  })

  test("Intelligence — /intelligence I1 field surface", async ({ page }) => {
    const pageContext = page.waitForResponse(
      (r) => r.url().includes("/api/intelligence/page-context") && r.status() === 200,
      { timeout: 90_000 },
    )
    await page.goto("/intelligence")
    await expect(page).not.toHaveURL(/\/login/)
    await pageContext.catch(() => undefined)
    await expect(page.getByTestId("intelligence-i1-i2")).toBeVisible({ timeout: 90_000 })
    await expect(page.getByTestId("intel-i3-matrix")).toBeVisible({ timeout: 90_000 })
    await expect(page.getByTestId("intel-i2-stream")).toHaveCount(0)
  })

  test("Intelligence — lens switch Learns → Predicts", async ({ page }) => {
    await page.goto("/intelligence")
    await expect(page).not.toHaveURL(/\/login/)
    const map = page.getByTestId("intelligence-map-canvas")
    await expect(map).toBeVisible({ timeout: 90_000 })
    // Prod OverviewLivingMap uses "Intelligence lenses"; harness uses "Intelligence map lenses".
    const lensBar = page
      .getByRole("tablist", { name: /Intelligence (map )?lenses/i })
      .first()
    await expect(lensBar).toBeVisible({ timeout: 30_000 })
    for (const label of ["Learns", "Predicts"] as const) {
      await lensBar.getByRole("tab", { name: label }).click()
      await expect(lensBar.getByRole("tab", { name: label, selected: true })).toBeVisible()
      await expect(map).toBeVisible()
    }
  })

  test("Activity — /activity heading + shell", async ({ page }) => {
    await assertAuthenticatedRoute(page, "/activity", () =>
      page.getByRole("heading", { name: "Activity" }),
    )
  })

  test("Navigation B — rail expand + pin labels", async ({ page }) => {
    await page.goto("/home")
    await expect(page).not.toHaveURL(/\/login/)
    const rail = page.getByTestId("nav-rail-b")
    await expect(rail).toBeVisible({ timeout: 60_000 })
    await expect(rail).toHaveAttribute("data-nav-expanded", "false")
    const pin = page.getByTestId("nav-pin-labels")
    await expect(pin).toBeVisible({ timeout: 30_000 })
    await pin.click({ force: true })
    await expect(rail).toHaveAttribute("data-nav-expanded", "true")
    await expect(page.getByTestId("sidebar-link-activity")).toBeVisible()
    await expect(page).not.toHaveURL(/\/login/)
  })

  test("Agents — /agents team surface", async ({ page }) => {
    await assertAuthenticatedRoute(page, "/agents", () =>
      page.getByRole("heading", { name: /agents|team/i }).first(),
    )
  })

  test("Relationships — learning relationships mount", async ({ page }) => {
    await page.goto("/intelligence/learning")
    await expect(page).not.toHaveURL(/\/login/)
    const heading = page.getByRole("heading", { name: /learning|relationships/i }).first()
    const canvas = page.locator("[data-testid='relationships-canvas'], [data-relationships-workspace]").first()
    await expect(heading.or(canvas)).toBeVisible({ timeout: 90_000 })
  })

  test("Workflows — /workflows builder", async ({ page }) => {
    await assertAuthenticatedRoute(page, "/workflows", () =>
      page.getByRole("heading", { name: /workflow/i }).first(),
    )
  })

  test("Connectors — /connectors hub list-first", async ({ page }) => {
    await page.goto("/connectors")
    await expect(page).not.toHaveURL(/\/login/)
    await expect(page.getByTestId("connectors-hub-b")).toBeVisible({ timeout: 90_000 })
    await expect(page.getByRole("heading", { name: /connector/i }).first()).toBeVisible({
      timeout: 90_000,
    })
  })

  test("Sources — /sources table", async ({ page }) => {
    await assertAuthenticatedRoute(page, "/sources", () =>
      page.getByRole("heading", { name: /source/i }).first(),
    )
  })

  test("Approvals — /approvals queue", async ({ page }) => {
    await assertAuthenticatedRoute(page, "/approvals", () =>
      page.getByRole("heading", { name: /approval/i }).first(),
    )
  })

  test("Marketplace — /marketplace catalog", async ({ page }) => {
    await assertAuthenticatedRoute(page, "/marketplace", () =>
      page.getByRole("heading", { name: /marketplace|pack/i }).first(),
    )
  })

  test("Models — /models catalog", async ({ page }) => {
    await assertAuthenticatedRoute(page, "/models", () =>
      page.getByRole("heading", { name: /model/i }).first(),
    )
  })

  test("Settings — /settings shell", async ({ page }) => {
    await page.goto("/settings")
    await expect(page).not.toHaveURL(/\/login/)
    // AppShell title may not be an h1; prove settings section nav mounted.
    await expect(page.locator("aside nav").first()).toBeVisible({ timeout: 60_000 })
    await expect(page.getByRole("navigation", { name: "Settings sections" })).toBeVisible({
      timeout: 60_000,
    })
  })

  test("AI Workspace — /ai stays authenticated", async ({ page }) => {
    await page.goto("/ai")
    await expect(page).not.toHaveURL(/\/login/)
    const landing = page.locator("[data-gravitre-ai-landing]")
    const composer = page.locator("textarea").first()
    await expect(landing.or(composer)).toBeVisible({ timeout: 90_000 })
  })
})
