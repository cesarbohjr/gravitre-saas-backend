import { describe, expect, it } from "vitest"
import {
  deriveCanonicalPresentation,
  toCanonicalPresentationState,
  toLegacyPresentationMode,
} from "@/lib/gravitre-ai-presentation"
import { modeToRemember, restoreTargetMode } from "@/lib/chat-window-state"

describe("presentation compatibility mapping", () => {
  it("maps canonical names onto shipped React-state values", () => {
    expect(toLegacyPresentationMode("minimized")).toBe("helper")
    expect(toLegacyPresentationMode("compact")).toBe("float")
    expect(toLegacyPresentationMode("expanded")).toBe("expanded")
    expect(toLegacyPresentationMode("fullscreen")).toBe("fullscreen")
  })

  it("maps shipped names onto canonical states", () => {
    expect(toCanonicalPresentationState("helper")).toBe("minimized")
    expect(toCanonicalPresentationState("float")).toBe("compact")
    expect(toCanonicalPresentationState("expanded")).toBe("expanded")
    expect(toCanonicalPresentationState("fullscreen")).toBe("fullscreen")
  })

  it("round-trips every canonical state through the legacy layer", () => {
    for (const canonical of ["minimized", "compact", "expanded", "fullscreen"] as const) {
      expect(toCanonicalPresentationState(toLegacyPresentationMode(canonical))).toBe(canonical)
    }
  })

  it("treats a closed workspace as minimized even if the last mode was fullscreen", () => {
    expect(
      deriveCanonicalPresentation({ floatWorkspaceOpen: false, mode: "fullscreen" }),
    ).toBe("minimized")
    expect(deriveCanonicalPresentation({ floatWorkspaceOpen: true, mode: "float" })).toBe("compact")
    expect(deriveCanonicalPresentation({ floatWorkspaceOpen: true, mode: "compact" })).toBe(
      "compact",
    )
    expect(deriveCanonicalPresentation({ floatWorkspaceOpen: true, mode: "helper" })).toBe(
      "compact",
    )
  })

  it("restore still returns the user to compact rather than the launcher", () => {
    expect(restoreTargetMode("helper")).toBe("float")
    expect(restoreTargetMode(toLegacyPresentationMode("minimized"))).toBe("float")
    expect(modeToRemember("helper")).toBe("float")
    expect(restoreTargetMode("fullscreen")).toBe("fullscreen")
    expect(restoreTargetMode("float")).toBe("float")
  })
})
