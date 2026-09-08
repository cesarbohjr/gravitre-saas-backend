import { describe, expect, it } from "vitest"
import {
  AudioPreRollBuffer,
  concatPcm16,
  resolveMicCaptureTuning,
  updateSpeechGate,
  voiceMicPhase1FlagsFromStatus,
} from "@/lib/voice-mic-capture"
import { inferMicFieldProfile as inferFromDevices } from "@/lib/voice-mic-devices"

describe("voiceMicPhase1FlagsFromStatus", () => {
  it("defaults off when phase1 block missing", () => {
    expect(voiceMicPhase1FlagsFromStatus(null)).toEqual({
      agcV2: false,
      micTelemetry: false,
      prerollV2: false,
      prerollMs: 300,
      micSelector: false,
      nearFarV1: false,
    })
  })

  it("reads server flags", () => {
    expect(
      voiceMicPhase1FlagsFromStatus({
        tts_enabled: true,
        stt_enabled: true,
        phase1_mic_capture: {
          agc_v2: true,
          mic_telemetry_v1: true,
          preroll_v2: true,
          preroll_ms: 400,
          mic_selector_v1: true,
          near_far_v1: true,
        },
      }),
    ).toMatchObject({
      agcV2: true,
      micTelemetry: true,
      prerollV2: true,
      prerollMs: 400,
    })
  })
})

describe("AudioPreRollBuffer", () => {
  it("retains only the last N ms of samples", () => {
    const buf = new AudioPreRollBuffer(100, 16000)
    buf.push(new Int16Array(800))
    buf.push(new Int16Array(800))
    buf.push(new Int16Array(800))
    const snap = buf.snapshot()
    expect(snap.length).toBeLessThanOrEqual(1600)
    expect(snap.length).toBeGreaterThan(0)
  })
})

describe("updateSpeechGate", () => {
  it("activates on speech onset and flushes pre-roll once", () => {
    const tuning = resolveMicCaptureTuning(
      { agcV2: false, micTelemetry: false, prerollV2: true, prerollMs: 300, micSelector: false, nearFarV1: false },
      "far_field",
    )
    let gate = updateSpeechGate({ active: false, prerollFlushed: false }, 0.002, tuning)
    expect(gate.active).toBe(false)
    gate = updateSpeechGate(gate, tuning.speechOnsetRms + 0.01, tuning)
    expect(gate.active).toBe(true)
    expect(gate.prerollFlushed).toBe(false)
  })
})

describe("concatPcm16", () => {
  it("joins two buffers", () => {
    const a = new Int16Array([1, 2])
    const b = new Int16Array([3])
    expect(Array.from(concatPcm16(a, b))).toEqual([1, 2, 3])
  })
})

describe("mic field profile inference", () => {
  it("classifies headset as near field", () => {
    expect(inferFromDevices("USB Headset Microphone")).toBe("near_field")
  })
  it("classifies built-in as far field", () => {
    expect(inferFromDevices("Built-in Microphone (Realtek)")).toBe("far_field")
  })
})
