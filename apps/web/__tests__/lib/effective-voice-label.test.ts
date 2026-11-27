import { describe, expect, it } from "vitest"
import { effectiveVoiceLabel } from "@/lib/effective-voice-label"

describe("session voice identity labels", () => {
  it("never presents a conflicting key as the effective explicit voice", () => {
    expect(effectiveVoiceLabel({ voice_id: "CaseSensitive", voice_key: "sarah" })).toBe("Assigned voice")
  })
  it("keeps custom identity opaque and recognizes key-only profiles", () => {
    expect(effectiveVoiceLabel({ voice_source: "custom_voice_v3", voice_id: "CustomCase" })).toBe("Custom voice")
    expect(effectiveVoiceLabel({ voice_key: "sarah" })).toBe("Configured voice")
    expect(effectiveVoiceLabel()).toBe("Default spoken voice")
  })
})
