import { test, expect } from "@playwright/test"

test.describe("Voice duplex browser pipeline", () => {
  test("mic open streams PCM and completes a session turn", async ({ page, context }) => {
    await context.grantPermissions(["microphone"])
    await page.goto("/e2e/voice-duplex")

    const harness = page.getByTestId("voice-duplex-harness")
    await expect(harness).toBeVisible()

    await page.getByTestId("voice-duplex-start").click()

    await expect
      .poll(async () => harness.getAttribute("data-ws-open"), { timeout: 15_000 })
      .toBe("true")

    await expect
      .poll(async () => Number(await harness.getAttribute("data-pcm-bytes")), { timeout: 15_000 })
      .toBeGreaterThan(0)

    await expect
      .poll(async () => harness.getAttribute("data-session-turn"), { timeout: 20_000 })
      .toBe("true")
  })
})
