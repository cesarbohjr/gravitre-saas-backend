import { describe, expect, it } from "vitest"
import {
  DEFAULT_MAX_ACTIONS_PER_HOUR,
  guardrailLimitsConfigFromBody,
  normalizeMaxActionsPerHour,
  readGuardrailLimitsFromConfig,
} from "@/lib/agent-config-catalog"
import { agentSystemKeys, connectedAppsFromConnectors } from "@/lib/agent-connected-apps"

describe("agent guardrail limits", () => {
  it("clamps and defaults the hourly action limit", () => {
    expect(normalizeMaxActionsPerHour("25")).toBe(25)
    expect(normalizeMaxActionsPerHour(0)).toBe(DEFAULT_MAX_ACTIONS_PER_HOUR)
    expect(normalizeMaxActionsPerHour("abc")).toBe(DEFAULT_MAX_ACTIONS_PER_HOUR)
    expect(normalizeMaxActionsPerHour(999999)).toBe(10000)
  })

  it("round-trips through config", () => {
    const stored = guardrailLimitsConfigFromBody({ guardrailLimits: { maxActionsPerHour: 12 } })
    expect(stored).toEqual({ max_actions_per_hour: 12 })
    expect(readGuardrailLimitsFromConfig({ guardrail_limits: stored })).toEqual({ maxActionsPerHour: 12 })
    expect(readGuardrailLimitsFromConfig(null)).toEqual({ maxActionsPerHour: DEFAULT_MAX_ACTIONS_PER_HOUR })
    expect(guardrailLimitsConfigFromBody({ name: "x" })).toBeNull()
  })
})

describe("agent connected apps", () => {
  it("keeps one connected row per vendor key", () => {
    const apps = connectedAppsFromConnectors([
      { status: "connected", type: "hubspot", name: "HubSpot" },
      { status: "active", type: "hubspot", name: "HubSpot (2)" },
      { status: "error", type: "slack", name: "Slack" },
      { status: "healthy", type: "Google Analytics", name: "GA" },
    ])
    expect(apps.map((a) => a.id)).toEqual(["google_analytics", "hubspot"])
  })

  it("maps older saved display names to integration keys", () => {
    expect(agentSystemKeys(["HubSpot", "Google Analytics", "Microsoft 365", "hubspot"])).toEqual([
      "hubspot",
      "google_analytics",
      "microsoft365",
    ])
  })
})
