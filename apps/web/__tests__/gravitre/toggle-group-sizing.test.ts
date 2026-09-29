// @vitest-environment jsdom
import { act, createElement } from "react"
import { createRoot } from "react-dom/client"
import { describe, expect, it } from "vitest"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"

;(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true

describe("ToggleGroupItem sizing", () => {
  it("sizes each segment to its label so longer labels are not clipped in a w-fit group", () => {
    const container = document.createElement("div")
    document.body.appendChild(container)
    const root = createRoot(container)
    act(() => {
      root.render(
        createElement(
          ToggleGroup,
          { type: "single", variant: "outline", size: "sm" },
          createElement(ToggleGroupItem, { value: "conversation" }, "Conversation"),
          createElement(ToggleGroupItem, { value: "work" }, "Work"),
        ),
      )
    })
    for (const item of container.querySelectorAll("[data-slot=toggle-group-item]")) {
      expect(item.className).toContain("flex-auto")
      expect(item.className).not.toMatch(/(^|\s)flex-1(\s|$)/)
      expect(item.className).not.toMatch(/(^|\s)min-w-0(\s|$)/)
    }
    act(() => root.unmount())
    container.remove()
  })
})
