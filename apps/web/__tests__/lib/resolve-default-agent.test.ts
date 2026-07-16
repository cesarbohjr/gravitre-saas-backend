import { describe, expect, it } from "vitest"
import {
  collectInstalledAgentIds,
  resolveCouncilAgentDefaults,
  resolveDefaultAgentId,
  resolveSwarmAgentDefaults,
} from "@/lib/resolve-default-agent"

describe("collectInstalledAgentIds", () => {
  it("collects agentId, agentIds, and agent entity installs", () => {
    const ids = collectInstalledAgentIds([
      { status: "active", metadata: { agentId: "a1", agentIds: ["a1", "a2"] } },
      { status: "active", installedEntityType: "agent", installedEntityId: "a3" },
      { status: "uninstalled", metadata: { agentId: "gone" } },
      { status: "failed", metadata: { agentId: "bad" } },
    ])
    expect(ids).toEqual(["a1", "a2", "a3"])
  })
})

describe("resolveDefaultAgentId", () => {
  const agents = [
    { id: "plain", name: "Plain", status: "active" },
    { id: "pack", name: "Pack Agent", status: "active", config: { marketplaceAssetId: "asset-1" } },
    { id: "idle", name: "Idle", status: "paused" },
  ]

  it("prefers explicit preferred id when present", () => {
    expect(
      resolveDefaultAgentId({
        agents,
        preferredAgentId: "plain",
        installedAgentIds: ["pack"],
      }),
    ).toBe("plain")
  })

  it("prefers installed pack agent over plain", () => {
    expect(resolveDefaultAgentId({ agents, installedAgentIds: ["pack"] })).toBe("pack")
  })

  it("falls back to pack-backed agent when installs empty", () => {
    expect(resolveDefaultAgentId({ agents, installedAgentIds: [] })).toBe("pack")
  })

  it("returns sole active agent", () => {
    expect(
      resolveDefaultAgentId({
        agents: [{ id: "only", status: "active" }],
        installedAgentIds: [],
      }),
    ).toBe("only")
  })

  it("returns null when no agents", () => {
    expect(resolveDefaultAgentId({ agents: [] })).toBeNull()
  })
})

describe("resolveSwarmAgentDefaults", () => {
  it("sets parent from pack and fills distinct subtask agents", () => {
    const result = resolveSwarmAgentDefaults({
      agents: [
        { id: "a", name: "A", status: "active", config: { packId: "p1" } },
        { id: "b", name: "B", status: "active" },
        { id: "c", name: "C", status: "active" },
      ],
      installedAgentIds: ["a", "b", "c"],
    })
    expect(result).toEqual({
      parentAgentId: "a",
      subtaskAgentIds: ["b", "c"],
    })
  })

  it("reuses parent for subtasks when only one agent exists", () => {
    const result = resolveSwarmAgentDefaults({
      agents: [{ id: "solo", status: "active", config: { marketplaceAssetId: "x" } }],
      installedAgentIds: ["solo"],
    })
    expect(result).toEqual({
      parentAgentId: "solo",
      subtaskAgentIds: ["solo"],
    })
  })
})

describe("resolveCouncilAgentDefaults", () => {
  it("maps org agents to council personas with real ids", () => {
    const council = resolveCouncilAgentDefaults(
      [
        { id: "u1", name: "Alpha", role: "Analyst", status: "active", config: { pack_id: "p" } },
        { id: "u2", name: "Beta", role: "Reviewer", status: "active" },
      ],
      ["u1", "u2"],
      3,
    )
    expect(council).toHaveLength(2)
    expect(council[0]).toMatchObject({ id: "u1", name: "Alpha", role: "Analyst" })
    expect(council[1]).toMatchObject({ id: "u2", name: "Beta" })
  })
})
