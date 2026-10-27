import { test, expect } from "@playwright/test"

/**
 * Regression reproduction for iPhone report: voice talks over the user, then
 * reopening the voice surface leaves it apparently active but silent.
 * The harness exercises the production duplex hook with a deterministic
 * microphone and mock Deepgram transport, not a physical iPhone microphone.
 */
test("voice can stop and reopen without becoming silently inactive", async ({ page, context }) => {
  await context.grantPermissions(["microphone"])
  await page.goto("/e2e/voice-duplex?transport=http")
  const harness = page.getByTestId("voice-duplex-harness")
  const toggle = page.getByTestId("voice-duplex-start")
  await expect(harness).toHaveAttribute("data-ready", "true")

  await toggle.click()
  await expect(harness).toHaveAttribute("data-active", "true", { timeout: 15000 })
  await expect(harness).toHaveAttribute("data-presence", "listening", { timeout: 15000 })
  const firstBytes = Number(await harness.getAttribute("data-pcm-bytes"))
  await expect.poll(async () => Number(await harness.getAttribute("data-pcm-bytes"))).toBeGreaterThan(firstBytes)

  // Interrupt the active session and immediately reopen, reproducing the
  // user's close/reopen sequence rather than merely reloading the page.
  await toggle.click()
  await expect(harness).toHaveAttribute("data-active", "false")
  await expect(harness).toHaveAttribute("data-presence", "idle")
  const beforeReopen = Number(await harness.getAttribute("data-pcm-bytes"))
  await toggle.click()
  await expect(harness).toHaveAttribute("data-active", "true", { timeout: 15000 })
  await expect(harness).toHaveAttribute("data-presence", "listening", { timeout: 15000 })
  await expect.poll(async () => Number(await harness.getAttribute("data-pcm-bytes")), { timeout: 15000 }).toBeGreaterThan(beforeReopen)
  await expect(harness).toHaveAttribute("data-last-error", "")
})
