import { describe, expect, it } from "vitest"
import {
  CHAT_CANVAS_THEME_IDS,
  DEFAULT_CHAT_CANVAS_THEME,
  isChatCanvasThemeId,
} from "@/lib/chat-canvas-themes"

describe("chat-canvas-themes", () => {
  it("exposes exactly eight theme ids", () => {
    expect(CHAT_CANVAS_THEME_IDS).toHaveLength(8)
  })

  it("validates theme ids", () => {
    expect(isChatCanvasThemeId(DEFAULT_CHAT_CANVAS_THEME)).toBe(true)
    expect(isChatCanvasThemeId("neon")).toBe(false)
  })
})
