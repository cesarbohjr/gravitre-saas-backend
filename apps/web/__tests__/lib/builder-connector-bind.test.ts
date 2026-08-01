import { describe, expect, it } from "vitest"
import {
  resolveConnectorBind,
  splitToolAction,
  connectorConfigWithBind,
  compiledConnectorAction,
} from "@/lib/workflows/builder-connector-bind"
import { evaluateNodeReadiness } from "@/lib/workflows/builder-node-readiness"

describe("builder-connector-bind", () => {
  it("splits apollo.lists.create", () => {
    expect(splitToolAction("apollo.lists.create")).toEqual({
      vendor: "apollo",
      selectedAction: "lists.create",
    })
  })

  it("hydrates marketplace invoke_tool config (connector + action)", () => {
    const bind = resolveConnectorBind({
      config: { connector: "apollo", action: "apollo.lists.create" },
    })
    expect(bind.vendor).toBe("apollo")
    expect(bind.selectedAction).toBe("lists.create")
    expect(bind.action).toBe("apollo.lists.create")
  })

  it("treats hydrated Apollo write node as ready", () => {
    const bind = resolveConnectorBind({
      config: { connector: "apollo", action: "apollo.lists.create", tool_action: "apollo.lists.create" },
    })
    const node = {
      id: "apollo_list_create",
      type: "connector" as const,
      name: "Apollo create list (write)",
      config: connectorConfigWithBind({}, bind),
      position: { x: 0, y: 0 },
      connections: [] as string[],
      vendor: bind.vendor,
      selectedAction: bind.selectedAction,
    }
    expect(evaluateNodeReadiness(node).ready).toBe(true)
  })

  it("persists action into config via connectorConfigWithBind", () => {
    const action = compiledConnectorAction("apollo", "lists.create")
    expect(action).toBe("apollo.lists.create")
    expect(
      connectorConfigWithBind(
        {},
        { vendor: "apollo", selectedAction: "lists.create", action },
      ),
    ).toMatchObject({
      vendor: "apollo",
      action: "apollo.lists.create",
      tool_action: "apollo.lists.create",
    })
  })
})
