import { describe, expect, it } from "vitest"
import { CONTINUE_AFTER_STOP_TEXT, isStopPlaceholder } from "@/lib/chat-continue"

describe("chat-continue", () => {
  it("recognizes the F1 stop placeholder", () => {
    expect(isStopPlaceholder("Stopped.")).toBe(true)
    expect(isStopPlaceholder("stopped")).toBe(true)
    expect(isStopPlaceholder("Here are two contacts")).toBe(false)
  })

  it("uses a plain Continue utterance, not a product claim", () => {
    expect(CONTINUE_AFTER_STOP_TEXT).toBe("Continue")
  })
})
