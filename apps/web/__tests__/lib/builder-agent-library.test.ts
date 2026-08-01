import { describe, expect, it } from "vitest"
import {
  agentLibrarySubtitle,
  agentNodeConfig,
  filterBuilderAgents,
  listAgentDepartments,
} from "@/lib/workflows/builder-agent-library"

const agents = [
  {
    id: "a1",
    name: "Lead Enrichment Coordinator",
    role: "Sales Development",
    department: "Sales",
    description: "Enrich lists",
    status: "active",
    capabilities: ["enrichment", "list_sync"],
  },
  {
    id: "a2",
    name: "AI Visibility Analyst",
    role: "analyst",
    department: "Marketing",
    status: "active",
    capabilities: ["brand_radar"],
  },
  {
    id: "a3",
    name: "Retired Bot",
    role: "analyst",
    department: "Ops",
    status: "inactive",
  },
]

describe("builder-agent-library", () => {
  it("filters by department, role, and free-text (incl. capabilities)", () => {
    expect(filterBuilderAgents(agents, { department: "Sales" }).map((a) => a.id)).toEqual(["a1"])
    expect(filterBuilderAgents(agents, { role: "analyst" }).map((a) => a.id)).toEqual(["a2"])
    expect(filterBuilderAgents(agents, { query: "enrichment" }).map((a) => a.id)).toEqual(["a1"])
    expect(filterBuilderAgents(agents, { query: "visibility" }).map((a) => a.id)).toEqual(["a2"])
  })

  it("lists departments from active agents only", () => {
    expect(listAgentDepartments(agents)).toEqual(["Marketing", "Sales"])
  })

  it("builds bindable agent node config", () => {
    expect(agentNodeConfig(agents[0])).toEqual({
      agent_id: "a1",
      agentId: "a1",
      task: "Enrich lists",
    })
    expect(agentLibrarySubtitle(agents[0])).toBe("Sales Development · Sales")
  })
})
