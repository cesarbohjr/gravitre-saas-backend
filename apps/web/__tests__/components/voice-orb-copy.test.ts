import { describe, expect, it } from "vitest"
import { resolveVoiceOrbCopy } from "@/components/gravitre/assistant/voice-presentation"

/**
 * Regression cover for the reported "mic mute button isn't working" screenshot,
 * where the orb read "<agent> voice paused" above "<agent> voice channel is live".
 *
 * The bug had two halves. This file pins the copy half: heading and subtitle used
 * to derive from unrelated inputs (micActive vs speaker), so they could contradict
 * each other. The behavioural half -- the mic button calling toggle() and ending
 * the session -- lives in the composer.
 */
describe("resolveVoiceOrbCopy", () => {
  it("does not claim the channel is live while the mic is muted", () => {
    // The exact reported state: muted, so not capturing, but still connected and
    // still the user's floor.
    const { phase, label, subtitle } = resolveVoiceOrbCopy({
      micMuted: true,
      micActive: false,
      speaker: "user",
      sessionLive: true,
      agentLabel: "Friendly Assistant",
    })

    expect(phase).toBe("muted")
    expect(label).toBe("Microphone muted")
    expect(subtitle).not.toMatch(/live/i)
    expect(subtitle).toMatch(/unmute/i)
  })

  it("never pairs a paused-sounding heading with a live-sounding subtitle", () => {
    // Exhaustive over the inputs that drove the two strings independently. Any
    // future branch that reintroduces the contradiction fails here.
    for (const playbackBlocked of [false, true]) {
      for (const micMuted of [false, true]) {
        for (const micActive of [false, true]) {
          for (const sessionLive of [false, true]) {
            for (const speaker of ["user", "agent"] as const) {
              const { label, subtitle } = resolveVoiceOrbCopy({
                playbackBlocked,
                micMuted,
                micActive,
                sessionLive,
                speaker,
                agentLabel: "Friendly Assistant",
              })
              const headingSaysStopped = /paused|muted|ended|blocked/i.test(label)
              const subtitleSaysLive = /channel is live/i.test(subtitle)
              expect(
                headingSaysStopped && subtitleSaysLive,
                `contradiction for ${JSON.stringify({ playbackBlocked, micMuted, micActive, sessionLive, speaker })}: "${label}" / "${subtitle}"`,
              ).toBe(false)
            }
          }
        }
      }
    }
  })

  it("reports listening while connected and unmuted", () => {
    const { phase, subtitle } = resolveVoiceOrbCopy({
      micActive: true,
      speaker: "user",
      sessionLive: true,
      agentLabel: "Friendly Assistant",
    })
    expect(phase).toBe("listening")
    expect(subtitle).toBe("Friendly Assistant voice channel is live")
  })

  it("distinguishes an ended session from a muted one", () => {
    const ended = resolveVoiceOrbCopy({ micActive: false, speaker: "user", sessionLive: false })
    const muted = resolveVoiceOrbCopy({ micActive: false, micMuted: true, speaker: "user", sessionLive: true })
    expect(ended.phase).toBe("ended")
    expect(muted.phase).toBe("muted")
    expect(ended.label).not.toBe(muted.label)
  })

  it("prioritises blocked playback over mute, since silence is the louder failure", () => {
    const { phase } = resolveVoiceOrbCopy({ playbackBlocked: true, micMuted: true, speaker: "user" })
    expect(phase).toBe("blocked")
  })
})
