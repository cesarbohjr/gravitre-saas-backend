import { describe, expect, it } from "vitest"

import { resolveVoiceOrbCopy } from "@/components/gravitre/assistant/voice-presentation"

/**
 * Reported symptom: "Says voice ended but it was never listening or responding."
 *
 * Both "error" and "disconnected" leave micActive and sessionLive false, which
 * landed on the same phase as a session the user deliberately hung up. So a
 * failure rendered as a calm "Gravitre voice ended / Tap the mic to start
 * talking again" and the person had no way to tell a dead session from a
 * finished one.
 */
describe("resolveVoiceOrbCopy failure states", () => {
  const dead = { speaker: "user" as const, micActive: false, sessionLive: false }

  it("does not call a failed session 'ended'", () => {
    const copy = resolveVoiceOrbCopy({ ...dead, presence: "error" })
    expect(copy.phase).toBe("failed")
    expect(copy.label).not.toMatch(/ended/i)
    expect(copy.label).toBe("Voice couldn't connect")
  })

  it("shows the server's own explanation when there is one", () => {
    const copy = resolveVoiceOrbCopy({
      ...dead,
      presence: "error",
      failureReason: "Voice minutes exhausted for this organization.",
    })
    expect(copy.subtitle).toBe("Voice minutes exhausted for this organization.")
  })

  it("falls back to something actionable when the server said nothing", () => {
    const copy = resolveVoiceOrbCopy({ ...dead, presence: "error" })
    expect(copy.subtitle).toBe("Tap the mic to try again")
  })

  it("ignores a blank reason rather than rendering empty space", () => {
    const copy = resolveVoiceOrbCopy({ ...dead, presence: "error", failureReason: "   " })
    expect(copy.subtitle).toBe("Tap the mic to try again")
  })

  it("distinguishes a dropped channel from a failure", () => {
    const copy = resolveVoiceOrbCopy({ ...dead, presence: "disconnected" })
    expect(copy.phase).toBe("reconnecting")
    expect(copy.label).toBe("Reconnecting…")
  })

  it("still calls a genuinely finished session 'ended'", () => {
    // presence idle with nothing live is a real ending, and must keep the calm copy.
    const copy = resolveVoiceOrbCopy({ ...dead, presence: "idle" })
    expect(copy.phase).toBe("ended")
    expect(copy.label).toBe("Gravitre voice ended")
  })

  it("keeps blocked playback ahead of failure, since it is actionable", () => {
    const copy = resolveVoiceOrbCopy({ ...dead, presence: "error", playbackBlocked: true })
    expect(copy.phase).toBe("blocked")
  })

  it("reports failure even while the mic is muted", () => {
    // Muted is about the mic; failed is about the session. The session losing is
    // the more important fact, and a muted-looking orb on a dead session is how
    // this became invisible in the first place.
    const copy = resolveVoiceOrbCopy({ ...dead, presence: "error", micMuted: true })
    expect(copy.phase).toBe("failed")
  })

  it("leaves healthy sessions untouched", () => {
    expect(
      resolveVoiceOrbCopy({ speaker: "user", micActive: true, presence: "listening" }).phase,
    ).toBe("listening")
    expect(
      resolveVoiceOrbCopy({ speaker: "agent", micActive: false, presence: "speaking" }).phase,
    ).toBe("replying")
  })
})
