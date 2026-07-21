import { describe, expect, it } from "vitest"
import { textForSpeech } from "@/lib/speech-text"
import {
  mapSpeechRecognitionError,
  speechRecognitionErrorMessage,
} from "@/lib/speech-recognition"

describe("textForSpeech", () => {
  it("speaks plain sentences unchanged", () => {
    expect(textForSpeech("Hello there. How can I help?")).toBe(
      "Hello there. How can I help?",
    )
  })

  it("skips fenced code blocks", () => {
    expect(
      textForSpeech("Here is the answer.\n\n```python\nprint('hi')\n```\n\nDone."),
    ).toBe("Here is the answer. Done.")
  })

  it("replaces raw links with speakable text", () => {
    expect(textForSpeech("See https://example.com/docs for details.")).toBe(
      "See a link for details.",
    )
  })

  it("uses markdown link labels when present", () => {
    expect(textForSpeech("Read [the docs](https://example.com) next.")).toBe(
      "Read the docs next.",
    )
  })

  it("strips headings and list markers", () => {
    expect(textForSpeech("## Summary\n\n- First point\n- Second point")).toBe(
      "Summary First point Second point",
    )
  })

  it("returns empty string when only code remains", () => {
    expect(textForSpeech("```js\nconst x = 1\n```")).toBe("")
  })
})

describe("speechRecognitionErrorMessage", () => {
  it("maps permission denial clearly", () => {
    expect(speechRecognitionErrorMessage("not-allowed")).toMatch(/denied/i)
  })

  it("maps silence clearly", () => {
    expect(speechRecognitionErrorMessage("no-speech")).toMatch(/No speech detected/i)
  })

  it("returns empty string for user abort", () => {
    expect(speechRecognitionErrorMessage("aborted")).toBe("")
  })
})

describe("mapSpeechRecognitionError", () => {
  it("passes through known browser codes", () => {
    expect(mapSpeechRecognitionError("network")).toBe("network")
  })

  it("falls back to unknown", () => {
    expect(mapSpeechRecognitionError("something-weird")).toBe("unknown")
  })
})
