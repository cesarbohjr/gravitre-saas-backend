import { describe, expect, it } from "vitest"
import {
  AMPLITUDE_ATTACK,
  AMPLITUDE_RELEASE,
  NORMALIZE_MIN_PEAK,
  ORB_STATE_LABELS,
  USER_SPEAKING_HANG_MS,
  USER_SPEAKING_ONSET,
  USER_SPEAKING_RELEASE,
  createAmplitudeNormalizer,
  normalizeAmplitude,
  orbStateIsAudioDriven,
  orbStateSpeaker,
  resolveOrbState,
  smoothAmplitude,
  type OrbStateInput,
  type VoiceOrbState,
} from "@/lib/voice-orb-state"
import type { VoicePresenceState } from "@/components/gravitre/assistant/voice-session-presence"

const ALL_ORB_STATES: VoiceOrbState[] = [
  "idle",
  "listening",
  "user_speaking",
  "thinking",
  "agent_speaking",
  "interrupted",
  "error",
]

const ALL_PRESENCE: VoicePresenceState[] = [
  "idle",
  "listening",
  "understanding",
  "thinking",
  "speaking",
  "interrupted",
  "disconnected",
  "error",
]

function input(overrides: Partial<OrbStateInput> = {}): OrbStateInput {
  return {
    presence: "listening",
    micLevel: 0,
    agentLevel: null,
    micMuted: false,
    sessionLive: true,
    previous: "listening",
    quietForMs: 0,
    ...overrides,
  }
}

describe("microphone energy drives USER_SPEAKING", () => {
  it("enters user_speaking when mic energy crosses the onset threshold", () => {
    // The gap this fills: presence stays "listening" while someone talks, until
    // the STT provider emits a boundary. Energy is what actually knows.
    expect(resolveOrbState(input({ micLevel: USER_SPEAKING_ONSET }))).toBe("user_speaking")
    expect(resolveOrbState(input({ micLevel: 0.9 }))).toBe("user_speaking")
  })

  it("does not enter user_speaking below the onset threshold", () => {
    expect(resolveOrbState(input({ micLevel: USER_SPEAKING_ONSET - 0.01 }))).toBe("listening")
    expect(resolveOrbState(input({ micLevel: 0 }))).toBe("listening")
  })

  it("latches through the dips between syllables", () => {
    // A single threshold makes the orb chatter several times a second, because
    // speech energy dips between syllables.
    const midSyllableDip = input({
      micLevel: (USER_SPEAKING_ONSET + USER_SPEAKING_RELEASE) / 2,
      previous: "user_speaking",
    })
    expect(resolveOrbState(midSyllableDip)).toBe("user_speaking")
  })

  it("holds through a short pause and releases after the hang time", () => {
    const quiet = { micLevel: 0, previous: "user_speaking" as VoiceOrbState }
    expect(resolveOrbState(input({ ...quiet, quietForMs: 0 }))).toBe("user_speaking")
    expect(resolveOrbState(input({ ...quiet, quietForMs: USER_SPEAKING_HANG_MS - 1 }))).toBe(
      "user_speaking",
    )
    expect(resolveOrbState(input({ ...quiet, quietForMs: USER_SPEAKING_HANG_MS }))).toBe("listening")
  })

  it("cannot report speaking while the mic is muted, however loud the room is", () => {
    expect(resolveOrbState(input({ micLevel: 1, micMuted: true }))).toBe("listening")
    expect(resolveOrbState(input({ micLevel: 1, micMuted: true, previous: "user_speaking" }))).toBe(
      "listening",
    )
  })

  it("falls back to a session state when there is nothing measured", () => {
    expect(resolveOrbState(input({ micLevel: null }))).toBe("listening")
    expect(resolveOrbState(input({ micLevel: null, presence: "idle" }))).toBe("idle")
  })
})

describe("agent playback outranks microphone energy", () => {
  it("reports agent_speaking from playback presence", () => {
    expect(resolveOrbState(input({ presence: "speaking" }))).toBe("agent_speaking")
  })

  it("reports agent_speaking from measured playback energy", () => {
    expect(resolveOrbState(input({ agentLevel: USER_SPEAKING_ONSET }))).toBe("agent_speaking")
  })

  it("does not mistake the agent's own voice in the room for the user talking", () => {
    // The mic hears the speakers. Treating that as the user taking the floor is
    // how an orb ends up depicting the wrong speaker mid-reply.
    const state = resolveOrbState(input({ presence: "speaking", micLevel: 0.95 }))
    expect(state).toBe("agent_speaking")
  })
})

describe("session states outrank sound", () => {
  it("never paints over an error with a loud room", () => {
    expect(resolveOrbState(input({ presence: "error", micLevel: 1 }))).toBe("error")
    expect(resolveOrbState(input({ presence: "error", agentLevel: 1 }))).toBe("error")
  })

  it("keeps interruption visible while the mic is still hot", () => {
    expect(resolveOrbState(input({ presence: "interrupted", micLevel: 1 }))).toBe("interrupted")
  })

  it("shows a reconnect as interrupted rather than a hard error", () => {
    // The session intends to be live and is retrying; a hard error for a
    // sub-second blip would be its own bug.
    expect(resolveOrbState(input({ presence: "disconnected" }))).toBe("interrupted")
  })

  it("treats understanding as thinking, since both are the agent working", () => {
    expect(resolveOrbState(input({ presence: "understanding", micLevel: 1 }))).toBe("thinking")
    expect(resolveOrbState(input({ presence: "thinking" }))).toBe("thinking")
  })

  it("is idle when no session is live, whatever the mic reports", () => {
    expect(resolveOrbState(input({ sessionLive: false, micLevel: 1 }))).toBe("idle")
  })
})

describe("total coverage", () => {
  it("returns a valid state for every presence value", () => {
    for (const presence of ALL_PRESENCE) {
      for (const previous of ALL_ORB_STATES) {
        for (const micLevel of [null, 0, 0.5, 1]) {
          const state = resolveOrbState(input({ presence, previous, micLevel }))
          expect(ALL_ORB_STATES, `presence=${presence} previous=${previous}`).toContain(state)
        }
      }
    }
  })

  it("labels every state, since none may be conveyed by colour or motion alone", () => {
    for (const state of ALL_ORB_STATES) {
      expect(ORB_STATE_LABELS[state]).toBeTruthy()
    }
  })

  it("colours only the user's own speech as the user", () => {
    expect(orbStateSpeaker("user_speaking")).toBe("user")
    for (const state of ALL_ORB_STATES.filter((s) => s !== "user_speaking")) {
      expect(orbStateSpeaker(state)).toBe("agent")
    }
  })

  it("marks exactly the sound-driven states as audio driven", () => {
    expect(orbStateIsAudioDriven("user_speaking")).toBe(true)
    expect(orbStateIsAudioDriven("agent_speaking")).toBe(true)
    expect(orbStateIsAudioDriven("listening")).toBe(true)
    // These are session facts, not sound.
    expect(orbStateIsAudioDriven("idle")).toBe(false)
    expect(orbStateIsAudioDriven("thinking")).toBe(false)
    expect(orbStateIsAudioDriven("error")).toBe(false)
    expect(orbStateIsAudioDriven("interrupted")).toBe(false)
  })
})

describe("smoothing", () => {
  it("rises faster than it falls", () => {
    // A slow attack feels laggy on a speech onset; a fast release stutters
    // between syllables.
    expect(AMPLITUDE_ATTACK).toBeGreaterThan(AMPLITUDE_RELEASE)
    const rise = smoothAmplitude(0, 1)
    const fall = 1 - smoothAmplitude(1, 0)
    expect(rise).toBeGreaterThan(fall)
  })

  it("converges towards the target without overshooting", () => {
    let value = 0
    for (let i = 0; i < 200; i += 1) value = smoothAmplitude(value, 1)
    expect(value).toBeGreaterThan(0.99)
    expect(value).toBeLessThanOrEqual(1)
  })

  it("stays in range for hostile input", () => {
    for (const bad of [Number.NaN, Number.POSITIVE_INFINITY, -5, 9]) {
      const out = smoothAmplitude(0.5, bad)
      expect(out).toBeGreaterThanOrEqual(0)
      expect(out).toBeLessThanOrEqual(1)
    }
  })
})

describe("normalization", () => {
  it("makes a quiet microphone visible", () => {
    // Without this a quiet mic barely moves the orb, which reads as broken
    // rather than quiet.
    const n = createAmplitudeNormalizer()
    let out = 0
    for (let i = 0; i < 500; i += 1) out = normalizeAmplitude(n, 0.14)
    expect(out).toBeGreaterThan(0.9)
  })

  it("does not amplify silence into motion", () => {
    const n = createAmplitudeNormalizer()
    for (let i = 0; i < 500; i += 1) normalizeAmplitude(n, 0)
    expect(normalizeAmplitude(n, 0)).toBe(0)
    expect(n.peak).toBeGreaterThanOrEqual(NORMALIZE_MIN_PEAK)
  })

  it("recovers its range after a shout", () => {
    const n = createAmplitudeNormalizer()
    normalizeAmplitude(n, 1)
    const rightAfter = normalizeAmplitude(n, 0.2)
    for (let i = 0; i < 2000; i += 1) normalizeAmplitude(n, 0.2)
    expect(normalizeAmplitude(n, 0.2)).toBeGreaterThan(rightAfter)
  })

  it("never leaves 0-1", () => {
    const n = createAmplitudeNormalizer()
    for (const raw of [0, 0.001, 0.5, 1, 4, Number.NaN, -1]) {
      const out = normalizeAmplitude(n, raw)
      expect(out).toBeGreaterThanOrEqual(0)
      expect(out).toBeLessThanOrEqual(1)
    }
  })
})
