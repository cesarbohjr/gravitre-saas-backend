import { test, expect } from "@playwright/test"

test.describe("Voice duplex browser pipeline", () => {
  test("mic open streams PCM and completes a session turn", async ({ page, context }) => {
    await context.grantPermissions(["microphone"])
    await page.route("**/api/voice/stt/live-token", async (route) => {
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ ws_url: "wss://api.deepgram.com/v1/listen?model=nova-2", access_token: "harness-token", authorization: "Bearer harness-token", expires_in_seconds: 60, encoding: "linear16", sample_rate: 16000, provider: "deepgram" }) })
    })
    await page.route("**/api/voice/turn-taking/event", async (route) => {
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ state: {}, finalized_transcript: "hello harness" }) })
    })
    await page.route("**/api/voice/session/turn", async (route) => {
      await route.fulfill({ status: 200, contentType: "application/x-ndjson", body: JSON.stringify({ type: "voice.turn.complete", text: "Harness heard you.", transcript: "Harness heard you." }) + "\\n" })
    })
    await page.goto("/e2e/voice-duplex")

    const harness = page.getByTestId("voice-duplex-harness")
    await expect(harness).toBeVisible()
    // The mocks are installed in a client effect. Waiting for the explicit
    // readiness bit prevents Playwright from clicking during hydration before
    // WebSocket/fetch/AudioContext have been replaced.
    await expect.poll(async () => harness.getAttribute("data-ready"), { timeout: 10_000 }).toBe("true")

    await page.getByTestId("voice-duplex-start").click()

    await expect.poll(async () => harness.getAttribute("data-ws-open"), { timeout: 15_000 }).toBe("true").catch(async (err) => {
      const state = {
        wsOpen: await harness.getAttribute("data-ws-open"),
        presence: await harness.getAttribute("data-presence"),
        active: await harness.getAttribute("data-active"),
        error: await harness.getAttribute("data-last-error"),
        audioContext: await harness.getAttribute("data-capture-ctx-state"),
      }
      throw new Error(`Voice duplex socket did not open. Harness state: ${JSON.stringify(state)}\n${err instanceof Error ? err.message : String(err)}`)
    })

    // The harness constructs the capture context autoplay-blocked, so this only
    // reaches "running" if the hook explicitly resumes it.
    await expect
      .poll(async () => harness.getAttribute("data-capture-ctx-state"), { timeout: 15_000 })
      .toBe("running")

    await expect
      .poll(async () => Number(await harness.getAttribute("data-pcm-bytes")), { timeout: 15_000 })
      .toBeGreaterThan(0)

    await expect
      .poll(async () => harness.getAttribute("data-session-turn"), { timeout: 20_000 })
      .toBe("true")
  })
})
