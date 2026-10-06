import { describe, expect, it } from "vitest"
import { deliverableExport, parseDeliverable, parseRawJsonEdit } from "@/lib/assignment-deliverable"
import { buildEditorContent, initialEditorState } from "@/components/assignments/deliverable-editor"

const structured = {
  summary: "Pipeline is healthy.",
  recommendations: ["Follow up with Acme", "Close stale deals"],
  confidence: 0.82,
  meta: { source: "crm", ids: [1, 2] },
}

describe("deliverable editor", () => {
  it("opens structured output in readable field mode, not raw JSON", () => {
    const parsed = parseDeliverable(JSON.stringify(structured))
    const state = initialEditorState(parsed)
    expect(state.mode).toBe("fields")
    const kinds = Object.fromEntries(state.fields.map((f) => [f.key, f.kind]))
    expect(kinds.summary).toBe("text")
    expect(kinds.recommendations).toBe("list")
    expect(kinds.meta).toBe("locked")
  })

  it("saves edited fields while preserving non-text fields exactly", () => {
    const parsed = parseDeliverable(JSON.stringify(structured))
    const state = initialEditorState(parsed)
    const fields = state.fields.map((f) =>
      f.key === "summary" ? { ...f, text: "Pipeline needs attention." } : f.key === "recommendations" ? { ...f, text: "Call Acme\n\nArchive stale deals" } : f,
    )
    const result = buildEditorContent(parsed, "fields", fields, state.raw)
    expect(result.ok).toBe(true)
    if (!result.ok) return
    const saved = JSON.parse(result.content)
    expect(saved.summary).toBe("Pipeline needs attention.")
    expect(saved.recommendations).toEqual(["Call Acme", "Archive stale deals"])
    expect(saved.confidence).toBe(0.82)
    expect(saved.meta).toEqual(structured.meta)
  })

  it("an unedited round-trip matches the baseline (no spurious changes)", () => {
    const parsed = parseDeliverable(JSON.stringify(structured))
    const state = initialEditorState(parsed)
    const result = buildEditorContent(parsed, state.mode, state.fields, state.raw)
    expect(result.ok && result.content).toBe(state.baseline)
  })

  it("rejects invalid raw JSON instead of saving it", () => {
    const parsed = parseDeliverable(JSON.stringify(structured))
    const result = buildEditorContent(parsed, "raw", [], "{ not json")
    expect(result.ok).toBe(false)
    expect(parseRawJsonEdit("[1,2]").ok).toBe(true)
  })

  it("treats plain text as text and refuses an empty save", () => {
    const parsed = parseDeliverable("Just a plain answer.")
    const state = initialEditorState(parsed)
    expect(state.mode).toBe("text")
    expect(buildEditorContent(parsed, "text", [], "   ").ok).toBe(false)
    const ok = buildEditorContent(parsed, "text", [], " Edited answer. ")
    expect(ok.ok && ok.content).toBe("Edited answer.")
  })
})

describe("deliverableExport", () => {
  it("exports a JSON string deliverable byte-for-byte", () => {
    const raw = `{"summary":"A",  "n": 1}`
    const exported = deliverableExport(parseDeliverable(raw))
    expect(exported.body).toBe(raw)
  })

  it("exports plain text as .txt unchanged", () => {
    const exported = deliverableExport(parseDeliverable("Hello\n\nWorld"))
    expect(exported).toMatchObject({ body: "Hello\n\nWorld", extension: "txt" })
  })
})
