import { describe, expect, it } from "vitest"
import {
  buildForecasts,
  forecastAreas,
  horizonToX,
  layoutTimeline,
  parseHorizonDays,
  summarizeForecasts,
  type FailureAlertWithEvidence,
} from "@/components/intelligence/forecasts/forecast-model"

const authAlert: FailureAlertWithEvidence = {
  id: "alert-1",
  workflowId: "wf-1",
  stepId: "s1",
  connectorId: "conn-9",
  alertType: "auth_disconnected",
  severity: "critical",
  title: "hubspot authentication required",
  message: "Connector auth status is 'pending_auth'. Workflow step 'Account signals' is likely to fail on the next run.",
  confidence: 0.92,
  status: "open",
  evidence: { authStatus: "pending_auth", connectorType: "hubspot", stepName: "Account signals" },
}

describe("Forecasts model", () => {
  it("turns a workflow auth alert into a risk with a reconnect action from the alert itself", () => {
    const [forecast] = buildForecasts({ failureAlerts: [authAlert] })
    expect(forecast.kind).toBe("risk")
    expect(forecast.title).toBe("HubSpot sign-in needed")
    expect(forecast.whenLabel).toBe("Next run")
    expect(forecast.needsYouNow).toBe(true)
    expect(forecast.action).toEqual({ type: "link", label: "Reconnect HubSpot", href: "/connectors/conn-9" })
    expect(forecast.alertId).toBe("alert-1")
  })

  it("drops snapshot predictions that echo an open failure alert and keeps unknown values unknown", () => {
    const rows = buildForecasts({
      failureAlerts: [authAlert],
      predictions: [
        { id: "x", type: "risk", businessStatement: "hubspot authentication required", subject: "hubspot authentication required", semanticKey: "k1", evidence: [] },
        { id: "y", type: "opportunity", businessStatement: "Lead mix: more enterprise leads", subject: "Lead mix", semanticKey: "k2", department: "sales", evidence: ["Three leads"], recommendedActions: ["Route to senior reps"] },
      ],
    })
    expect(rows).toHaveLength(2)
    const opp = rows.find((row) => row.kind === "opportunity")!
    expect(opp.title).toBe("Lead mix")
    expect(opp.summary).toBe("more enterprise leads")
    expect(opp.confidence).toBeNull()
    expect(opp.horizonDays).toBeNull()
    expect(opp.whenLabel).toBe("No date yet")
    expect(opp.area).toBe("Sales")
    expect(opp.action).toMatchObject({ type: "ask", label: "Route to senior reps" })
    expect(forecastAreas(rows)).toEqual(["Workflows", "Sales"])
    expect(summarizeForecasts(rows)).toMatchObject({ active: 2, risks: 1, opportunities: 1, needYouNow: 1, needEvidence: 0 })
  })

  it("parses horizons and places them on the timeline", () => {
    expect(parseHorizonDays("7d")).toBe(7)
    expect(parseHorizonDays("2 weeks")).toBe(14)
    expect(parseHorizonDays("next_run")).toBe(0)
    expect(parseHorizonDays(undefined)).toBeNull()
    expect(horizonToX(0)).toBe(0)
    expect(horizonToX(14)).toBe(24)
    expect(horizonToX(30)).toBe(48)
    expect(horizonToX(null)).toBe(90)
    const dots = layoutTimeline(buildForecasts({ failureAlerts: [authAlert] }))
    expect(dots).toHaveLength(1)
    expect(dots[0].side).toBe("above")
  })
})
