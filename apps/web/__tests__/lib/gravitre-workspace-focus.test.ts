import { describe, expect, it } from "vitest"
import { buildWorkspaceFocusPayload } from "@/lib/gravitre-workspace-focus"

describe("buildWorkspaceFocusPayload", () => {
  it("omits payload when there is no route and no selection", () => {
    expect(buildWorkspaceFocusPayload({ surface: "", route: "", selected: null })).toBeUndefined()
  })

  it("sends route without treating label as the object identity", () => {
    const payload = buildWorkspaceFocusPayload({
      surface: "ai_chat",
      route: "/intelligence",
      selected: { kind: "entity", id: "acme", label: "Acme Corporation" },
    })
    expect(payload?.selection?.object_id).toBe("acme")
    expect(payload?.selection?.object_type).toBe("entity")
    expect(payload?.selection?.label).toBe("Acme Corporation")
    expect(payload?.route).toBe("/intelligence")
  })
  it.each(["goal", "source", "assignment", "training-dataset", "training-job", "multi-agent-run"])("carries %s identity without its content", (kind) => {
    const payload = buildWorkspaceFocusPayload({
      surface: "ai_chat", route: "/training",
      selected: { kind, id: "selected-id", label: "  " + "x".repeat(220) + "  " },
    })
    expect(payload?.selection).toEqual({ object_type: kind, object_id: "selected-id", label: "x".repeat(200) })
  })
})
