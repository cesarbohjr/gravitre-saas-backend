import { describe, expect, it } from "vitest"
import {
  CHAT_WINDOW_CONTROLS,
  CHAT_WINDOW_CONTROL_LABELS,
  controlsForSurface,
  isExitControl,
  modeToRemember,
  restoreTargetMode,
  surfaceHasExit,
  type ChatSurface,
  type ChatWindowMode,
} from "@/lib/chat-window-state"

const ALL_SURFACES: ChatSurface[] = ["float", "expanded", "fullscreen", "embedded"]
const ALL_MODES: ChatWindowMode[] = ["helper", "float", "expanded", "fullscreen"]

describe("no surface is a dead-end", () => {
  // The invariant the whole module exists for. Iterating the full surface list
  // rather than spot-checking is the point: a surface added later is covered
  // automatically, which is how `/ai` lost its controls unnoticed.
  it.each(ALL_SURFACES)("%s offers at least one way out", (surface) => {
    expect(surfaceHasExit(surface)).toBe(true)
  })

  it("covers every surface in the manifest, with no empty entries", () => {
    expect(Object.keys(CHAT_WINDOW_CONTROLS).sort()).toEqual([...ALL_SURFACES].sort())
    for (const surface of ALL_SURFACES) {
      expect(controlsForSurface(surface).length).toBeGreaterThan(0)
    }
  })

  it("gives the embedded /ai surface an exit, which it previously had none of", () => {
    // /ai also hides the floating launcher by design, so a control-less embedded
    // page was a chat you could see and not leave.
    expect(controlsForSurface("embedded")).toContain("openAsFloat")
    expect(surfaceHasExit("embedded")).toBe(true)
  })

  it("labels every control, so none can ship as an unnamed icon button", () => {
    for (const surface of ALL_SURFACES) {
      for (const id of controlsForSurface(surface)) {
        expect(CHAT_WINDOW_CONTROL_LABELS[id]).toBeTruthy()
      }
    }
  })
})

describe("per-surface control manifest", () => {
  it("fullscreen can always be left", () => {
    const ids = controlsForSurface("fullscreen")
    expect(ids).toContain("exitFullscreen")
    expect(ids).toContain("collapseToFloat")
    expect(ids).toContain("minimizeToHelper")
  })

  it("the windowed float can reach fullscreen directly", () => {
    // Previously float offered only Expand and Minimize, so fullscreen took two
    // steps for no reason.
    expect(controlsForSurface("float")).toContain("fullscreen")
  })

  it("does not offer fullscreen while already fullscreen, or exit while not", () => {
    expect(controlsForSurface("fullscreen")).not.toContain("fullscreen")
    expect(controlsForSurface("float")).not.toContain("exitFullscreen")
    expect(controlsForSurface("expanded")).not.toContain("exitFullscreen")
  })

  it("classifies exit controls and non-exit controls correctly", () => {
    expect(isExitControl("minimizeToHelper")).toBe(true)
    expect(isExitControl("collapseToFloat")).toBe(true)
    expect(isExitControl("exitFullscreen")).toBe(true)
    expect(isExitControl("openAsFloat")).toBe(true)
    // Growing the window is not a way out of it.
    expect(isExitControl("expand")).toBe(false)
    expect(isExitControl("fullscreen")).toBe(false)
  })
})

describe("restoring the previous mode", () => {
  it("returns the user to the mode they left", () => {
    // The reported bug: closing to the launcher discarded the mode and the
    // launcher always reopened "float", so fullscreen work came back as a small
    // window.
    expect(restoreTargetMode("fullscreen")).toBe("fullscreen")
    expect(restoreTargetMode("expanded")).toBe("expanded")
    expect(restoreTargetMode("float")).toBe("float")
  })

  it("falls back to the windowed mode when there is nothing to restore", () => {
    expect(restoreTargetMode(null)).toBe("float")
    expect(restoreTargetMode(undefined)).toBe("float")
  })

  it("never restores to the launcher itself, which would look like a dead click", () => {
    expect(restoreTargetMode("helper")).toBe("float")
  })

  it("never remembers 'helper' as the mode to come back to", () => {
    expect(modeToRemember("helper")).toBe("float")
  })

  it("remembers every real mode unchanged", () => {
    for (const mode of ["float", "expanded", "fullscreen"] as ChatWindowMode[]) {
      expect(modeToRemember(mode)).toBe(mode)
    }
  })

  it("round-trips every mode to something restorable and non-helper", () => {
    for (const mode of ALL_MODES) {
      const restored = restoreTargetMode(modeToRemember(mode))
      expect(restored).not.toBe("helper")
      expect(ALL_MODES).toContain(restored)
    }
  })
})
