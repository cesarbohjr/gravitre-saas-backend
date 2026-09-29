import { describe, expect, it } from "vitest"
import {
  GRAVITRE_AI_COMPOSITION_STORAGE_KEY,
  readCompositionPreference,
  resolveWorkspaceComposition,
  writeCompositionPreference,
} from "@/lib/gravitre-ai-composition"

describe("resolveWorkspaceComposition", () => {
  it("offers only Conversation when there is no work", () => {
    expect(resolveWorkspaceComposition({ preferred: null, hasWork: false, approvalVisible: false })).toEqual({
      composition: "conversation",
      available: ["conversation"],
      reason: null,
    })
    expect(resolveWorkspaceComposition({ preferred: "work", hasWork: false, approvalVisible: false }).reason).toBe("no-work")
  })

  it("defaults to Split when work exists (the pre-Slice-1 behaviour)", () => {
    expect(resolveWorkspaceComposition({ preferred: null, hasWork: true, approvalVisible: false }).composition).toBe("split")
  })

  it("honours a remembered preference when work exists", () => {
    expect(resolveWorkspaceComposition({ preferred: "work", hasWork: true, approvalVisible: false }).composition).toBe("work")
    expect(
      resolveWorkspaceComposition({ preferred: "conversation", hasWork: true, approvalVisible: false }).composition,
    ).toBe("conversation")
  })

  it("never hides a visible approval: Work falls back to Split", () => {
    const resolved = resolveWorkspaceComposition({ preferred: "work", hasWork: true, approvalVisible: true })
    expect(resolved.composition).toBe("split")
    expect(resolved.available).not.toContain("work")
    expect(resolved.reason).toBe("approval-visible")
  })
})

describe("composition preference storage", () => {
  it("round-trips valid values and ignores junk", () => {
    const store = new Map<string, string>()
    const storage = {
      getItem: (k: string) => store.get(k) ?? null,
      setItem: (k: string, v: string) => void store.set(k, v),
    }
    expect(readCompositionPreference(storage)).toBeNull()
    writeCompositionPreference("work", storage)
    expect(readCompositionPreference(storage)).toBe("work")
    store.set(GRAVITRE_AI_COMPOSITION_STORAGE_KEY, "dashboard")
    expect(readCompositionPreference(storage)).toBeNull()
  })
})
