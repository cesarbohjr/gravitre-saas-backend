import { readFileSync } from "node:fs"
import { resolve } from "node:path"
import { describe, expect, it } from "vitest"

const webRoot = resolve(__dirname, "../..")
const duplex = readFileSync(resolve(webRoot, "hooks/use-voice-duplex-session.ts"), "utf8")
const workspace = readFileSync(resolve(webRoot, "app/ai/_components/ai-workspace.tsx"), "utf8")

describe("ChatGPT/Claude-class live voice interaction contract", () => {
  it("commits turns inside a persistent duplex session", () => {
    expect(duplex).toMatch(/assistant_turn\.complete/)
    expect(duplex).toMatch(/onTurnComplete/)
    expect(duplex).toMatch(/duplex_transport_owned: true/)
  })

  it("supports live barge-in instead of waiting for socket teardown", () => {
    expect(duplex).toMatch(/bargeIn\(\)/)
    expect(duplex).toMatch(/speech\.interrupted/)
  })

  it("does not replay a turn already owned by live delivery", () => {
    expect(workspace).toMatch(/duplexOwnsTurn/)
    expect(workspace).toMatch(/lastSpokenMessageIdRef/)
  })

  it("keeps physical playback evidence distinct from text completion", () => {
    expect(duplex).toMatch(/browser_audio_playback_started/)
    expect(duplex).toMatch(/audibleAudioFramesRef/)
  })
})
