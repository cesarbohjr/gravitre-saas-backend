import { readFileSync } from "node:fs"
import { join } from "node:path"

import { describe, expect, it } from "vitest"

import { speechInterruptionKind } from "@/lib/voice-playback-progress"

describe("speech.interrupted intent", () => {
  it("separates speech_stop from a real barge-in", () => {
    expect(
      speechInterruptionKind({ type: "speech.interrupted", intent: "speech_stop", work_continues: true, reply_id: 3 }),
    ).toBe("speech_stop")
    expect(speechInterruptionKind({ type: "speech.interrupted", reply_id: 3 })).toBe("interrupt")
    expect(speechInterruptionKind({ type: "speech.interrupted", intent: "stop" })).toBe("interrupt")
  })
})

describe("duplex hook speech_stop handling", () => {
  const src = readFileSync(join(__dirname, "../../hooks/use-voice-duplex-session.ts"), "utf8")
  const start = src.indexOf('if (kind === "speech.interrupted" && speechInterruptionKind(msg) === "speech_stop")')
  const generic = src.indexOf('if (kind === "speech.interrupted") {', start)
  const block = src.slice(start, generic)

  it("is handled before the generic barge-in branch and returns", () => {
    expect(start).toBeGreaterThan(0)
    expect(generic).toBeGreaterThan(start)
    expect(block.trimEnd().endsWith("return\n        }") || /return\s*\}\s*$/.test(block)).toBe(true)
  })

  it("stops playback and drops the reply's audio by reply id", () => {
    expect(block).toContain("stopPcmPlayback()")
    expect(block).toMatch(/interruptedReplyIdRef\.current = Math\.max\(interruptedReplyIdRef\.current \?\? -1, replyId\)/)
    expect(block).toContain("speechMutedRef.current = true")
    expect(block).toContain("onSpeechStopped")
  })

  it("never resets or trims the visible reply text", () => {
    expect(block).not.toContain("assistantTextRef.current =")
    expect(block).not.toContain("assistantAnswerTextRef.current =")
    expect(block).not.toContain("onAssistantDelta")
    expect(block).not.toContain("onSpeechInterrupted")
    // The text is saved in full, so no interrupted playback report is sent.
    expect(block).not.toContain("sendPlaybackProgress")
  })

  it("keeps the HTTP TTS fallback from speaking a silenced reply", () => {
    const watchdog = src.slice(src.indexOf("const armAudioReplyWatchdog"), src.indexOf("const stopPcmPlayback"))
    expect(watchdog).toContain("!speechMutedRef.current")
  })

  it("shows each assistant_notice once", () => {
    const at = src.indexOf('if (kind === "assistant_notice")')
    expect(at).toBeGreaterThan(0)
    const notice = src.slice(at, src.indexOf("}", src.indexOf("onAssistantNotice", at)))
    expect(notice).toContain("noticesShownRef.current.has(key)")
    expect(notice).toContain("onAssistantNotice")
  })
})
