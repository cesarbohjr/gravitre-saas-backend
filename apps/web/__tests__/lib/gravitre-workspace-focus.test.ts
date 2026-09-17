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
})
