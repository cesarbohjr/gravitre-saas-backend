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
    await page.goto("/e2e/voice-duplex?transport=http")

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

  /**
   * Production transport. The browser runs the real hook's Pipecat branch over a
   * real WebSocket to backend/tests/e2e/pipecat_voice_harness_server.py, which
   * runs the production pipeline builder (serializer, transport, Flux turn
   * strategies, speculative processor, Cognitive LLM bridge, interrupt reporter,
   * durable history load and persistence). Deepgram, ElevenLabs, the reasoning
   * model and Supabase are replaced there; auth and the production router are
   * not covered.
   */
  test.describe("pipecat transport", () => {
    // The app CSP allows only wss: sockets; the local harness server is plain ws://.
    test.use({ bypassCSP: true })

    test("mic PCM reaches the server pipeline and the spoken reply plays back", async ({ page, context, request }) => {
      const wsBase = process.env.PIPECAT_HARNESS_URL ?? "http://127.0.0.1:8799"
      await context.grantPermissions(["microphone"])
      const before = await (await request.get(`${wsBase}/harness/state`)).json()

      await page.goto(`/e2e/voice-duplex?transport=pipecat&ws=${encodeURIComponent(wsBase)}`)
      const harness = page.getByTestId("voice-duplex-harness")
      await expect(harness).toHaveAttribute("data-transport", "pipecat")
      await expect.poll(async () => harness.getAttribute("data-ready"), { timeout: 10_000 }).toBe("true")

      await page.getByTestId("voice-duplex-start").click()

      const snapshot = async () => ({
        wsOpen: await harness.getAttribute("data-ws-open"),
        sessionReady: await harness.getAttribute("data-session-ready"),
        presence: await harness.getAttribute("data-presence"),
        error: await harness.getAttribute("data-last-error"),
        pcmBytes: await harness.getAttribute("data-pcm-bytes"),
        audioFrames: await harness.getAttribute("data-audio-frames"),
        captureCtx: await harness.getAttribute("data-capture-ctx-state"),
      })
      const explain = (what: string) => async (err: unknown) => {
        const server = await (await request.get(`${wsBase}/harness/state`)).json()
        throw new Error(`${what}. Harness state: ${JSON.stringify(await snapshot())}\nDispatch: ${JSON.stringify(server.dispatch_events ?? [])}\n${err instanceof Error ? err.message : String(err)}`)
      }

      await expect
        .poll(async () => harness.getAttribute("data-session-ready"), { timeout: 20_000 })
        .toBe("true")
        .catch(explain("Pipecat session never became ready"))

      // Explicit local capture runs on the actual post-duck Pipecat output.
      // This is a synthetic-provider browser integration check, NOT physical listening.
      const startCapture = page.getByTestId("acoustic-capture-start")
      await expect(startCapture).toBeEnabled()
      await startCapture.click()
      await expect(page.getByTestId("acoustic-capture-stop")).toBeEnabled()

      // The capture context only runs if the hook resumes it; no PCM flows otherwise.
      await expect
        .poll(async () => harness.getAttribute("data-capture-ctx-state"), { timeout: 15_000 })
        .toBe("running")
      await expect
        .poll(async () => Number(await harness.getAttribute("data-pcm-bytes")), { timeout: 15_000 })
        .toBeGreaterThan(0)

      // The server starts the user turn only after it has received real PCM, so a
      // completed turn proves browser capture reached the Pipecat pipeline.
      await expect
        .poll(async () => harness.getAttribute("data-assistant-text"), { timeout: 30_000 })
        .toBe("Acme is the priority account this quarter. Northwind comes next.")
        .catch(explain("Pipecat turn did not complete"))
      await expect(harness).toHaveAttribute("data-user-text", "which account is our priority this quarter")

      // Synthesized audio came back over the socket for playback.
      await expect
        .poll(async () => Number(await harness.getAttribute("data-audio-frames")), { timeout: 15_000 })
        .toBeGreaterThan(0)

      // Stopping creates local Blob URLs. These are never uploaded by the test.
      await page.getByTestId("acoustic-capture-stop").click()
      const audioDownload = page.getByRole("link", { name: "Save audio recording" })
      const timingDownload = page.getByRole("link", { name: "Save timing manifest" })
      await expect(audioDownload).toBeVisible()
      await expect(timingDownload).toBeVisible()
      const downloadPromise = page.waitForEvent("download")
      await timingDownload.click()
      const download = await downloadPromise
      expect(download.suggestedFilename()).toBe("gravitre-acoustic-timeline.json")

      // Server side: the turn ran on the durable seed and was persisted to the
      // same conversation the browser adopted.
      const after = await (await request.get(`${wsBase}/harness/state`)).json()
      const conversationId = after.seeded_conversation_id as string
      await expect(harness).toHaveAttribute("data-conversation-id", conversationId)
      expect(after.pcm_bytes_in).toBeGreaterThan(0)
      expect(after.llm_queries.length).toBeGreaterThan(before.llm_queries.length)
      const stages = (after.dispatch_events as Array<{stage: string; provisional?: boolean}> )
      expect(stages.filter(e => e.stage === "context_received" && !e.provisional)).toHaveLength(1)
      expect(stages.filter(e => e.stage === "context_accepted")).toHaveLength(1)
      expect(stages.filter(e => e.stage === "final_forwarded")).toHaveLength(1)
      expect(stages.filter(e => e.stage === "stop_forwarded")).toHaveLength(1)
      expect(after.prompt_calls).toBeGreaterThan(before.prompt_calls ?? 0)
      expect(after.guard_passes).toBeGreaterThan(before.guard_passes ?? 0)
      expect(after.durable_history_seen.at(-1)).toEqual([
        "Remember that Acme is the priority account.",
        "Noted, Acme is the priority.",
      ])
      const state = after.conversation_task_states.find((row: {id: string}) => row.id === conversationId)?.task_state
      expect(state?.recent_user_messages).toContain("which account is our priority this quarter")
      expect(state?.task_revision).toBeGreaterThan(0)
      const persisted = (after.conversation_messages as Array<{ conversation_id: string; role: string; content: string }>)
        .filter((row) => row.conversation_id === conversationId)
        .map((row) => [row.role, row.content])
      expect(persisted).toEqual(
        expect.arrayContaining([
          ["user", "which account is our priority this quarter"],
          ["assistant", "Acme is the priority account this quarter. Northwind comes next."],
        ]),
      )
    })
  })
})


test.describe("isolated live candidate browser journey", () => {
  test.use({ bypassCSP: true })
  test("live provider: browser PCM interruption and recovery", async ({ page,context,request }) => {
    test.skip(process.env.VOICE_BROWSER_LIVE_PROVIDER !== "1", "Explicit isolated provider run only")
    const base = process.env.PIPECAT_HARNESS_URL ?? "http://127.0.0.1:8799"
    const health = await (await request.get(base+"/health")).json()
    expect(health.mode).toBe("live")
    await context.grantPermissions(["microphone"])
    await page.goto("/e2e/voice-duplex?transport=pipecat&ws="+encodeURIComponent(base))
    const h = page.getByTestId("voice-duplex-harness")
    await expect(h).toHaveAttribute("data-ready","true")
    await page.getByTestId("voice-duplex-start").click()
    await expect(h).toHaveAttribute("data-session-ready","true")
    await page.getByTestId("acoustic-capture-start").click()
    await expect.poll(async()=>Number(await h.getAttribute("data-pcm-bytes"))).toBeGreaterThan(0)
    await expect.poll(async()=>Number(await h.getAttribute("data-latest-audio-reply")),{timeout:40000}).toBeGreaterThan(0)
    const old = Number(await h.getAttribute("data-latest-audio-reply"))
    await page.getByTestId("voice-duplex-interrupt").click()
    await expect.poll(async()=>Number(await h.getAttribute("data-interrupted-reply"))).toBeGreaterThanOrEqual(old)
    await page.evaluate(()=>window.__voiceDuplexHarness?.submitFinal("please give me the recovery status"))
    await expect.poll(async()=>Number(await h.getAttribute("data-latest-audio-reply")),{timeout:40000}).toBeGreaterThan(old)
    await expect(h).toHaveAttribute("data-assistant-text","The recovery response is ready. Thank you for waiting.",{timeout:40000})
    await expect(h).toHaveAttribute("data-ws-open","true")
    await expect(h).toHaveAttribute("data-stale-audio-frames","0")
    // Allow the short recovery reply to drain before stopping the local capture.
    await expect(h).toHaveAttribute("data-presence","listening",{timeout:40000})
    await page.getByTestId("acoustic-capture-stop").click()
    const manifestLink = page.getByRole("link",{name:"Save timing manifest"})
    await expect(manifestLink).toBeVisible()
    const manifest = await manifestLink.evaluate(async el=>await (await fetch((el as HTMLAnchorElement).href)).json())
    expect(manifest.limits.observations_truncated).toBe(false)
    const observations = manifest.observations as Array<{event:string;monotonic_ms:number;reply_id?:number}>
    const interrupt = observations.find(e=>e.event==="server_interrupted" && e.reply_id===old)
    expect(interrupt).toBeDefined()
    expect(observations.some(e=>e.event==="playback_started" && e.monotonic_ms<interrupt!.monotonic_ms)).toBe(true)
    expect(observations.some(e=>e.event==="playback_started" && e.monotonic_ms>interrupt!.monotonic_ms)).toBe(true)
    const state = await (await request.get(base+"/harness/state")).json()
    expect(state.provider_mode).toBe("live")
    expect(state.candidate_id).toBe(process.env.VOICE_BROWSER_CANDIDATE_ID)
    expect(state.candidate_model).toBe(process.env.VOICE_BROWSER_MODEL)
    expect(state.llm_queries).toContain("please give me the recovery status")
    await test.info().attach("live-browser-timing",{body:JSON.stringify({source_sha:process.env.GITHUB_SHA,candidate_id:state.candidate_id,model:state.candidate_model,manifest}),contentType:"application/json"})
  })
})
