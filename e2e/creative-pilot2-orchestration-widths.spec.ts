/**
 * Pilot 2 — Task Decomposition Field width + state smoke (DOM, not pixel).
 *
 * Widths from docs/design/gravitre-creative-pilot2-agent-orchestration.md §V.
 * Uses ?creativeState= (localhost-only) for deterministic frames.
 *
 * Run:
 *   PLAYWRIGHT_SKIP_BACKEND=1 PLAYWRIGHT_REUSE_SERVER=1 \
 *     pnpm exec playwright test e2e/creative-pilot2-orchestration-widths.spec.ts
 */
import { test, expect } from "@playwright/test"

const origin =
  process.env.PLAYWRIGHT_MARKETING_BASE_URL ??
  process.env.PLAYWRIGHT_BASE_URL ??
  "http://localhost:3001"

const WIDTHS = [390, 430, 768, 1024, 1280, 1440, 1728] as const

test.describe("Pilot 2 orchestration — width + creativeState smoke", () => {
  for (const width of WIDTHS) {
    test(`technology orchestration mounts @ ${width}`, async ({ page }) => {
      await page.setViewportSize({ width, height: width < 768 ? 844 : 900 })
      await page.emulateMedia({ reducedMotion: "reduce" })

      const url = new URL("/features/technology?creativeState=verify", origin).toString()
      const res = await page.goto(url, { waitUntil: "domcontentloaded" })
      expect(res?.ok() ?? false).toBe(true)

      const field = page.getByTestId("agent-orchestration-field")
      await expect(field).toBeVisible()

      const body = await page.locator("body").innerText()
      expect(body).toMatch(/Task Decomposition Field/i)
      expect(body).toMatch(/not a live run/i)

      // Reduced motion shows static information model
      await expect(page.getByTestId("orchestration-reduced")).toBeVisible()
    })
  }

  test("creativeState=verify freezes evidence on motion-enabled desktop", async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 800 })
    // Do not force reduced motion — exercise animated desktop layout + freeze
    const url = new URL("/features/technology?creativeState=verify", origin).toString()
    const res = await page.goto(url, { waitUntil: "domcontentloaded" })
    expect(res?.ok() ?? false).toBe(true)

    const field = page.getByTestId("agent-orchestration-field")
    await expect(field).toBeVisible()
    await expect(field).toHaveAttribute("data-creative-phase", "verify")
    await expect(field).toHaveAttribute("data-creative-frozen", "1")
    await expect(field).toHaveAttribute("data-creative-path-id", "path-write-follow-up")
    await expect(page.getByTestId("orchestration-evidence").first()).toBeVisible()
    await expect(page.getByTestId("orchestration-desktop")).toBeVisible()
  })

  test("creativeState=failure keeps research path successful (no scene flood)", async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 800 })
    const url = new URL("/features/technology?creativeState=failure", origin).toString()
    await page.goto(url, { waitUntil: "domcontentloaded" })

    const field = page.getByTestId("agent-orchestration-field")
    await expect(field).toHaveAttribute("data-creative-phase", "failure")
    await expect(field).toHaveAttribute("data-creative-path-research", "success")
    await expect(field).toHaveAttribute("data-creative-path-write", "error")
    await expect(field).toHaveAttribute("data-creative-scene-error", "0")
    await expect(page.getByTestId("orchestration-failure-mark")).toBeVisible()
  })

  test("creativeState=waiting then success path shares path id", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 })
    await page.goto(new URL("/features/technology?creativeState=waiting", origin).toString(), {
      waitUntil: "domcontentloaded",
    })
    const field = page.getByTestId("agent-orchestration-field")
    await expect(field).toHaveAttribute("data-creative-phase", "waiting")
    await expect(field).toHaveAttribute("data-creative-path-id", "path-write-follow-up")
    await expect(page.getByTestId("orchestration-waiting")).toBeVisible()
  })
})
