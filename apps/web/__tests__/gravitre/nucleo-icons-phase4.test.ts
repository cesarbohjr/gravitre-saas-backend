// @vitest-environment jsdom
/**
 * Phase 4 Nucleo-*style* icons (C1 icon-gap closure) — see
 * docs/delivery/ai-agent-floating-workspace-architecture-2026-09-07.md Part
 * C1. Confirms all 14 new icon components (11 requested affordances, with
 * Success/Error counted as 2 and Expand/Collapse/Minimize/Fullscreen
 * counted as 4 — see the Phase 4 delivery report for the exact mapping)
 * each render valid SVG output and are registered under a stable semantic
 * key in `SEMANTIC_NUCLEO`.
 *
 * Disclosure (also stated in semantic.tsx's file header and the Phase 4
 * delivery report): these are Nucleo-*style* constructions built to match
 * this repo's existing stroke/viewBox/corner conventions — NOT purchased or
 * licensed Nucleo-brand assets. This test does not assert brand
 * authenticity; it only asserts structural/registry correctness.
 */
import { createElement } from "react"
import { renderToStaticMarkup } from "react-dom/server"
import { describe, expect, it } from "vitest"

import {
  SEMANTIC_NUCLEO,
  NucleoExpand,
  NucleoCollapse,
  NucleoMinimize,
  NucleoFullscreen,
  NucleoMic,
  NucleoAttach,
  NucleoSend,
  NucleoRun,
  NucleoSuccess,
  NucleoError,
  NucleoSettings,
  NucleoHistory,
  NucleoNewChat,
  NucleoPanelToggle,
} from "@/components/icons/nucleo/semantic"

/** The 14 Phase 4 icon components, each paired with its expected registry key. */
const PHASE_4_ICONS: Array<{ name: string; Component: typeof NucleoExpand; registryKey: keyof typeof SEMANTIC_NUCLEO }> = [
  { name: "NucleoExpand", Component: NucleoExpand, registryKey: "expand" },
  { name: "NucleoCollapse", Component: NucleoCollapse, registryKey: "collapse" },
  { name: "NucleoMinimize", Component: NucleoMinimize, registryKey: "minimize" },
  { name: "NucleoFullscreen", Component: NucleoFullscreen, registryKey: "fullscreen" },
  { name: "NucleoMic", Component: NucleoMic, registryKey: "mic" },
  { name: "NucleoAttach", Component: NucleoAttach, registryKey: "attach" },
  { name: "NucleoSend", Component: NucleoSend, registryKey: "send" },
  { name: "NucleoRun", Component: NucleoRun, registryKey: "run" },
  { name: "NucleoSuccess", Component: NucleoSuccess, registryKey: "success" },
  { name: "NucleoError", Component: NucleoError, registryKey: "error" },
  { name: "NucleoSettings", Component: NucleoSettings, registryKey: "settings" },
  { name: "NucleoHistory", Component: NucleoHistory, registryKey: "history" },
  { name: "NucleoNewChat", Component: NucleoNewChat, registryKey: "newChat" },
  { name: "NucleoPanelToggle", Component: NucleoPanelToggle, registryKey: "panelToggle" },
]

describe("Phase 4 Nucleo-style icons — count", () => {
  it("ports exactly 14 new icon components, covering all ~11 requested affordances (Expand/Collapse/Minimize/Fullscreen=4, Success/Error=2, plus Mic/Attach/Send/Run/Settings/History/New-chat/Panel-toggle)", () => {
    expect(PHASE_4_ICONS).toHaveLength(14)
  })
})

describe.each(PHASE_4_ICONS)("$name", ({ Component, registryKey }) => {
  it("renders a valid, non-empty <svg> element", () => {
    const markup = renderToStaticMarkup(createElement(Component, { className: "h-4 w-4" }))
    expect(markup).toMatch(/^<svg[\s>]/)
    expect(markup).toContain("</svg>")
    // Real vector content, not an empty/placeholder shell.
    expect(markup).toMatch(/<(path|polyline|line|circle|rect|polygon)\b/)
  })

  it("forwards className and defaults to a 24x24 box (matches the existing Nucleo registry convention)", () => {
    const markup = renderToStaticMarkup(createElement(Component, { className: "custom-icon-class" }))
    expect(markup).toContain('class="custom-icon-class"')
    expect(markup).toContain('width="24"')
    expect(markup).toContain('height="24"')
  })

  it("respects an explicit size override, same as the pre-existing semantic icons", () => {
    const markup = renderToStaticMarkup(createElement(Component, { size: 16 }))
    expect(markup).toContain('width="16"')
    expect(markup).toContain('height="16"')
  })

  it(`is registered in SEMANTIC_NUCLEO under the "${String(registryKey)}" key, pointing at this exact component`, () => {
    expect(SEMANTIC_NUCLEO[registryKey]).toBe(Component)
  })
})

describe("SEMANTIC_NUCLEO registry — no accidental duplicate/missing keys", () => {
  it("has exactly one registry entry per Phase 4 icon, plus the pre-existing entries", () => {
    const registryKeys = Object.keys(SEMANTIC_NUCLEO)
    const phase4Keys = PHASE_4_ICONS.map((icon) => icon.registryKey)
    for (const key of phase4Keys) {
      expect(registryKeys).toContain(key)
    }
    // No two Phase 4 affordances collapsed onto the same key.
    expect(new Set(phase4Keys).size).toBe(phase4Keys.length)
  })
})
