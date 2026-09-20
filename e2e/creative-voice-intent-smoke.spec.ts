/**
 * Phase 9 — Voice Intent Field smoke on /features.
 */
import { test, expect } from "@playwright/test"

const origin =
  process.env.PLAYWRIGHT_MARKETING_BASE_URL ??
  process.env.PLAYWRIGHT_BASE_URL ??
  "http://localhost:3001"

test.describe("Voice Intent Field — features smoke", () => {
  test("mounts with honesty caption", async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 800 })
    await page.emulateMedia({ reducedMotion: "reduce" })
    const res = await page.goto(new URL("/features?voiceState=action", origin).toString(), {
      waitUntil: "domcontentloaded",
    })
    expect(res?.ok() ?? false).toBe(true)

    const field = page.getByTestId("voice-intent-field")
    await expect(field).toBeVisible()
    const body = await page.locator("body").innerText()
    expect(body).toMatch(/Waveform|Intent|Response/i)
    expect(body).toMatch(/Not proven duplex parity/i)
    await expect(page.getByTestId("voice-reduced")).toBeVisible()
  })

  test("voiceState=action freezes with turn path id", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 })
    await page.goto(new URL("/features?voiceState=action", origin).toString(), {
      waitUntil: "domcontentloaded",
    })
    const field = page.getByTestId("voice-intent-field")
    await expect(field).toHaveAttribute("data-creative-phase", "action")
    await expect(field).toHaveAttribute("data-voice-path-id", "path-voice-turn")
  })
})
