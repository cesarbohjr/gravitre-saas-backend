/**
 * Phase 11 — Creative Experience System AC width matrix (DOM smoke).
 * Covers signature mounts at bible §AC widths (subset: phone / tablet / desktop).
 */
import { test, expect } from "@playwright/test"

const origin =
  process.env.PLAYWRIGHT_MARKETING_BASE_URL ??
  process.env.PLAYWRIGHT_BASE_URL ??
  "http://localhost:3001"

const WIDTHS = [390, 768, 1280] as const

const MOUNTS = [
  {
    path: "/features/technology?gibeState=approve",
    testId: "gibe-learning-field",
    honesty: /Not auto policy rewrite/i,
  },
  {
    path: "/features?voiceState=action",
    testId: "voice-intent-field",
    honesty: /Not proven duplex parity/i,
  },
  {
    path: "/pricing?outcomesState=categories",
    testId: "outcomes-positioning-field",
    honesty: /No invented metrics/i,
  },
  {
    path: "/security?govState=approval",
    testId: "governed-execution-field",
    honesty: /Not a live compliance claim/i,
  },
  {
    path: "/docs/integrations?cfState=write_waiting",
    testId: "connector-fabric-field",
    honesty: /Not a live inventory/i,
  },
] as const

test.describe("Phase 11 creative AC width matrix", () => {
  for (const width of WIDTHS) {
    for (const mount of MOUNTS) {
      test(`${mount.testId} @ ${width}`, async ({ page }) => {
        await page.setViewportSize({ width, height: width < 768 ? 844 : 900 })
        await page.emulateMedia({ reducedMotion: "reduce" })
        const res = await page.goto(new URL(mount.path, origin).toString(), {
          waitUntil: "domcontentloaded",
        })
        expect(res?.ok() ?? false).toBe(true)
        const field = page.getByTestId(mount.testId)
        await expect(field).toBeVisible()
        await expect(field).toHaveAttribute("data-creative-quality", /fallback|low|medium|high/)
        const body = await page.locator("body").innerText()
        expect(body).toMatch(mount.honesty)
      })
    }
  }
})
