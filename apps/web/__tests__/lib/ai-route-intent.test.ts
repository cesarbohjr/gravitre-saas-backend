import { describe, expect, it } from "vitest"
import { heuristicRouteIntent, reconcileModelRouteIntent } from "@/lib/ai-route-intent"

describe("heuristicRouteIntent", () => {
  it("routes agent creation to conversational chat", () => {
    const result = heuristicRouteIntent("create a new agent for me")
    expect(result.mode).toBe("chat")
  })

  it("routes build workflow requests to conversational chat", () => {
    expect(heuristicRouteIntent("build a workflow that syncs HubSpot deals").mode).toBe("chat")
  })

  it("routes create an agent to chat", () => {
    expect(heuristicRouteIntent("create an agent").mode).toBe("chat")
  })

  it("routes incident remediation to execute", () => {
    expect(heuristicRouteIntent("fix the failed Salesforce sync").mode).toBe("execute")
  })

  it("routes explicit record lookup to find", () => {
    expect(heuristicRouteIntent("find my marketing agent").mode).toBe("find")
    expect(heuristicRouteIntent("show me workflows named onboarding").mode).toBe("find")
  })

  it("routes explanatory questions to chat", () => {
    expect(heuristicRouteIntent("how do agents work in Gravitre?").mode).toBe("chat")
    expect(heuristicRouteIntent("what is the difference between execute and chat").mode).toBe("chat")
  })

  it("does not treat create-agent-for-me as find", () => {
    const result = heuristicRouteIntent("create a new agent for me")
    expect(result.mode).not.toBe("find")
  })
})

describe("reconcileModelRouteIntent", () => {
  it("overrides mistaken find classification for create requests to chat", () => {
    const reconciled = reconcileModelRouteIntent("create a new agent for me", {
      mode: "find",
      confidence: 0.8,
      reason: "mentions agent",
    })
    expect(reconciled.mode).toBe("chat")
  })

  it("keeps execute mode for operational fixes even if model says chat", () => {
    const reconciled = reconcileModelRouteIntent("fix the failed nightly sync", {
      mode: "chat",
      confidence: 0.8,
      reason: "question",
    })
    expect(reconciled.mode).toBe("execute")
  })
})
