import { describe, expect, it } from "vitest"
import {
  DIALOGUE_MODE_LABELS,
  DURABLE_DIALOGUE_MODES,
  shouldShowDialogueModeChip,
} from "@/lib/dialogue-mode-labels"

const base = {
  isLastAssistant: true,
  turnInFlight: false,
  showInlineStatus: false,
}

describe("shouldShowDialogueModeChip", () => {
  it("hides a progressive label once the turn has finished", () => {
    // The reported defect: "Answering" left sitting above a finished reply.
    expect(shouldShowDialogueModeChip({ ...base, dialogueMode: "answer" })).toBe(false)
  })

  it("shows a progressive label while the turn is still in flight", () => {
    expect(
      shouldShowDialogueModeChip({ ...base, dialogueMode: "answer", turnInFlight: true }),
    ).toBe(true)
  })

  it.each(["analyze", "guide", "recommend", "research", "summarize", "execute", "simulate"])(
    "hides %s once the turn has finished",
    (mode) => {
      expect(shouldShowDialogueModeChip({ ...base, dialogueMode: mode })).toBe(false)
    },
  )

  it.each([...DURABLE_DIALOGUE_MODES])(
    "keeps %s after the turn finishes — it is still true",
    (mode) => {
      expect(shouldShowDialogueModeChip({ ...base, dialogueMode: mode })).toBe(true)
    },
  )

  it("never chips clarify — that renders as a ClarificationMessage", () => {
    expect(
      shouldShowDialogueModeChip({ ...base, dialogueMode: "clarify", turnInFlight: true }),
    ).toBe(false)
  })

  it("does not stack a chip on top of the inline thinking row", () => {
    expect(
      shouldShowDialogueModeChip({
        ...base,
        dialogueMode: "answer",
        turnInFlight: true,
        showInlineStatus: true,
      }),
    ).toBe(false)
  })

  it("only ever chips the newest assistant turn", () => {
    expect(
      shouldShowDialogueModeChip({
        ...base,
        isLastAssistant: false,
        dialogueMode: "confirm",
        turnInFlight: true,
      }),
    ).toBe(false)
  })

  it.each([null, undefined, ""])("renders nothing for %s mode", (mode) => {
    expect(
      shouldShowDialogueModeChip({ ...base, dialogueMode: mode, turnInFlight: true }),
    ).toBe(false)
  })

  it("every durable mode has a label that reads as an outstanding state", () => {
    // Guards the split: a durable mode whose label is present-progressive would
    // reintroduce the "still working" claim on a finished turn.
    for (const mode of DURABLE_DIALOGUE_MODES) {
      const label = DIALOGUE_MODE_LABELS[mode]
      if (!label) continue
      expect(label).not.toMatch(/ing$/)
    }
  })
})
