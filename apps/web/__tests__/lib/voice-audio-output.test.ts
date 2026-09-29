import { readFileSync } from "node:fs"
import { resolve } from "node:path"
import { describe, expect, it } from "vitest"

const webRoot = resolve(__dirname, "../..")
const hook = readFileSync(resolve(webRoot, "hooks/use-voice-duplex-session.ts"), "utf8")

describe("voice duplex audible output contract", () => {
  it("reuses the AudioContext unlocked by the user gesture", () => {
    expect(hook).toMatch(/getSharedPlaybackContext/)
    expect(hook).toMatch(/audioCtxSharedRef/)
    expect(hook).toMatch(/sharedOutput \?\? new AC\(\)/)
  })

  it("does not silently schedule Pipecat PCM onto a suspended context", () => {
    expect(hook).toMatch(/ctx\.state !== "running" \|\| playbackBlockedRef\.current/)
    expect(hook).toMatch(/pcmBlockedQueueRef/)
    expect(hook).toMatch(/setPlaybackBlocked\(true\)/)
  })

  it("retries queued PCM after an explicit sound-unlock gesture", () => {
    expect(hook).toMatch(/const queuedPcm = pcmBlockedQueueRef\.current\.splice\(0\)/)
    expect(hook).toMatch(/enqueuePcm\(chunk\.pcm, chunk\.sampleRate\)/)
  })

  it("does not close the shared output context when a voice session ends", () => {
    expect(hook).toMatch(/if \(!audioCtxSharedRef\.current\) \{\s*audioCtxRef\.current\?\.close\(\)/)
  })

  it("fails visibly when assistant text arrives but Pipecat never sends audio", () => {
    expect(hook).toMatch(/audioReplyWatchdogRef/)
    expect(hook).toMatch(/audioFramesReceivedRef/)
    expect(hook).toMatch(/Voice reply arrived, but no audio was received/)
    expect(hook).toMatch(/armAudioReplyWatchdog\(\)/)
    expect(hook).toMatch(/clearAudioReplyWatchdog\(\)/)
  })
})
