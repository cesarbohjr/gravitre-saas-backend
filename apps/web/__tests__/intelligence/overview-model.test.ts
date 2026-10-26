import { describe, expect, it } from "vitest"
import { dataReadiness, buildFeed } from "@/components/intelligence/overview/overview-model"
import type { Connector, IntelligencePageContextResponse } from "@/lib/api"

const app = (name: string, status = "active") => ({ id: name, name, status }) as unknown as Connector
const metrics = (links: number) => ({ knowledge: { knownEntities: 10, knownRelationships: links } }) as never

describe("Overview data readiness", () => {
  it("stays limited until two apps are connected and records are linked", () => {
    expect(dataReadiness({ connectors: [], metrics: null }).tier).toBe("limited")
    expect(dataReadiness({ connectors: [app("HubSpot")], metrics: metrics(5) }).tier).toBe("limited")
    expect(dataReadiness({ connectors: [app("HubSpot"), app("Stripe")], metrics: metrics(0) }).tier).toBe("limited")
  })

  it("is cross-system with linked records, and comprehensive at four apps with none waiting to sign in", () => {
    const two = dataReadiness({ connectors: [app("HubSpot"), app("Stripe")], metrics: metrics(12) })
    expect(two.tier).toBe("cross-system")
    expect(two.summary).toContain("12 records")
    const four = [app("HubSpot"), app("Stripe"), app("Slack"), app("Zendesk")]
    expect(dataReadiness({ connectors: four, metrics: metrics(12) }).tier).toBe("comprehensive")
    expect(dataReadiness({ connectors: [...four, app("Gmail", "auth_expired")], metrics: metrics(12) }).tier).toBe("cross-system")
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
