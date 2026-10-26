import { describe, expect, it } from "vitest"
import { dataReadiness, buildFeed, sevenAbilities } from "@/components/intelligence/overview/overview-model"
import type { Connector, IntelligencePageContextResponse } from "@/lib/api"

const app = (name: string, status = "active") => ({ id: name, name, status }) as unknown as Connector
const readiness = (vendors: string[], extra: Record<string, unknown> = {}) =>
  ({
    tier: vendors.length === 0 ? "insufficient" : vendors.length === 1 ? "limited" : "cross_system_candidate",
    connector_count: vendors.length,
    vendors,
    fresh_connectors: vendors,
    fresh_count: vendors.length,
    coverage_verified: false,
    comprehensive: false,
    recommended_connector_count: 3,
    missing_evidence: [],
    ...extra,
  }) as never

describe("Overview data readiness", () => {
  it("stays limited until two apps are usable", () => {
    expect(dataReadiness({ connectors: [], readiness: readiness([]) }).tier).toBe("limited")
    expect(dataReadiness({ connectors: [app("HubSpot")], readiness: readiness(["hubspot"]) }).tier).toBe("limited")
  })

  it("is cross-system from two apps and never comprehensive without verified coverage", () => {
    const connectors = [app("HubSpot"), app("Stripe"), app("Slack"), app("Zendesk")].map((c) => ({ ...c, vendor: c.name.toLowerCase() }))
    const four = dataReadiness({ connectors, readiness: readiness(["hubspot", "stripe", "slack", "zendesk"], { fresh_count: 3 }) })
    expect(four.tier).toBe("cross-system")
    expect(four.summary).toContain("HubSpot, Stripe")
    expect(four.summary).toContain("3 of 4 synced")
    const verified = dataReadiness({
      connectors,
      readiness: readiness(["hubspot", "stripe", "slack", "zendesk"], { comprehensive: true, coverage_verified: true }),
    })
    expect(verified.tier).toBe("comprehensive")
  })

  it("falls back to the connector list when the Overview contract is unavailable", () => {
    expect(dataReadiness({ connectors: [app("HubSpot"), app("Stripe")] }).tier).toBe("cross-system")
  })
})

describe("Overview seven abilities", () => {
  it("lists the router's seven abilities with the tenant's saved mode", () => {
    const list = sevenAbilities({ predictive: { mode: "proactive", description: "Estimates future risks." } })
    expect(list.map((a) => a.id)).toEqual(["contextual", "sentiment", "causal", "temporal", "relational", "adaptive", "predictive"])
    expect(list.at(-1)).toMatchObject({ mode: "proactive", detail: "Estimates future risks." })
    expect(list[0].mode).toBeNull()
  })
})

describe("Overview recent activity", () => {
  it("marks a forecast with suggested actions as a recommendation and drops a subject that repeats the title", () => {
    const ctx = {
      snapshot: {
        predictions: [
          { semanticKey: "renewal", subject: "Northwind may not renew", recommendedActions: ["Book a check-in"] },
        ],
      },
    } as unknown as IntelligencePageContextResponse
    const feed = buildFeed({
      ctx,
      forecasts: [{ key: "prediction:renewal", title: "Northwind may not renew", summary: "Usage fell", area: "Customer success", whenLabel: "In 2 months" }] as never,
      cards: [],
      routes: { forecasts: "/f", activity: "/a", reports: "/r", memory: "/m" },
    })
    const item = feed.find((row) => row.id === "forecast:prediction:renewal")
    expect(item?.kind).toBe("recommendation")
    expect(item?.suggestion).toBe("Book a check-in")
    expect(item?.meta).toEqual(["Customer success", "In 2 months"])
  })
})
