import { describe, expect, it } from "vitest"
import {
  CREATIVE_BRAND,
  CREATIVE_TOKENS,
  creativeDprCap,
  resolveCreativeQuality,
  shouldRunCreativeAnimation,
  snapshotCreativePerformance,
} from "@/components/marketing/creative"
import {
  topologyEdgeCount,
  topologyForCoreState,
} from "@/components/marketing/creative/primitives/relational-topology"
import { NETWORK_SCENARIOS } from "@/components/marketing/system/department-network/scenarios"

describe("creative experience tokens", () => {
  it("pins brand green exactly", () => {
    expect(CREATIVE_BRAND).toBe("#16a374")
    expect(CREATIVE_TOKENS.brand).toBe("#16a374")
  })
})

describe("creative performance manager", () => {
  it("falls back when reduced motion", () => {
    expect(resolveCreativeQuality({ reducedMotion: true })).toBe("fallback")
    expect(creativeDprCap("fallback")).toBe(1)
  })

  it("pauses animation when hidden or reduced", () => {
    expect(
      shouldRunCreativeAnimation({ reducedMotion: false, visible: true, documentHidden: true }),
    ).toBe(false)
    expect(
      shouldRunCreativeAnimation({ reducedMotion: true, visible: true, documentHidden: false }),
    ).toBe(false)
    expect(
      shouldRunCreativeAnimation({ reducedMotion: false, visible: true, documentHidden: false }),
    ).toBe(true)
  })

  it("snapshots quality + animate gate", () => {
    const snap = snapshotCreativePerformance({
      reducedMotion: false,
      visible: true,
      documentHidden: false,
    })
    expect(snap.quality).toBe("high")
    expect(snap.shouldAnimate).toBe(true)
    expect(snap.dprCap).toBe(2)
  })
})

describe("relational topology intelligence core", () => {
  it("changes geometry by state (not a static orb)", () => {
    const idle = topologyForCoreState("idle")
    const receiving = topologyForCoreState("receiving")
    const coordinating = topologyForCoreState("coordinating")
    const learned = topologyForCoreState("learned")

    expect(receiving.nodes.length).toBeGreaterThan(idle.nodes.length)
    expect(receiving.inboundIndex).toBeGreaterThanOrEqual(0)
    expect(coordinating.outboundIndices.length).toBeGreaterThan(0)
    expect(topologyEdgeCount("learned")).toBeGreaterThan(topologyEdgeCount("idle"))
    expect(learned.edges.length).toBeGreaterThan(idle.edges.length)
  })

  it("is deterministic across calls", () => {
    const a = topologyForCoreState("connecting")
    const b = topologyForCoreState("connecting")
    expect(a).toEqual(b)
  })
})

describe("departments converge pilot storyboard", () => {
  it("leads with organizational intelligence exchange", () => {
    expect(NETWORK_SCENARIOS[0]?.id).toBe("org-exchange")
    const beats = NETWORK_SCENARIOS[0]?.beats ?? []
    expect(beats.some((b) => b.type === "core" && b.state === "learned")).toBe(true)
    expect(beats.some((b) => b.type === "packet" && b.to === "finance")).toBe(true)
    expect(beats.some((b) => b.type === "packet" && b.to === "operations")).toBe(true)
  })
})

describe("pilot 2 orchestration storyboard", () => {
  it("keeps beat order and pauses into failure from parallel", async () => {
    const { nextPhase, PHASE_ORDER } = await import(
      "@/components/marketing/creative/scenes/agent-orchestration/storyboard"
    )
    expect(PHASE_ORDER).toEqual([
      "quiet",
      "intent",
      "understand",
      "plan",
      "delegate",
      "tools",
      "parallel",
      "waiting",
      "verify",
      "outcome",
      "learned",
    ])
    expect(nextPhase("parallel", "failure")).toBe("failure")
    expect(nextPhase("waiting", "success")).toBe("verify")
    expect(PHASE_ORDER).toContain("waiting")
    expect(PHASE_ORDER).toContain("verify")
  })

  it("continues the same governed write path id through approval", async () => {
    const { activePathId, GOVERNED_WRITE_PATH_ID, nextPhase } = await import(
      "@/components/marketing/creative/scenes/agent-orchestration/storyboard"
    )
    const waitingId = activePathId("waiting")
    const afterApprove = nextPhase("waiting", "success")
    expect(afterApprove).toBe("verify")
    expect(waitingId).toBe(GOVERNED_WRITE_PATH_ID)
    expect(activePathId(afterApprove)).toBe(waitingId)
  })

  it("shows evidence at VERIFY and keeps failure scoped to one path", async () => {
    const { phaseAtLeast, pathStatesForPhase } = await import(
      "@/components/marketing/creative/scenes/agent-orchestration/storyboard"
    )
    expect(phaseAtLeast("verify", "verify")).toBe(true)
    const failed = pathStatesForPhase("failure")
    expect(failed.research).toBe("success")
    expect(failed.write).toBe("error")
    expect(failed.research).not.toBe("error")
  })

  it("parses creativeState only on local hosts", async () => {
    const { parseCreativeStateParam } = await import(
      "@/components/marketing/creative/scenes/agent-orchestration/storyboard"
    )
    expect(parseCreativeStateParam("verify", { hostname: "localhost" })).toBe("verify")
    expect(parseCreativeStateParam("failure", { hostname: "127.0.0.1" })).toBe("failure")
    expect(parseCreativeStateParam("verify", { hostname: "gravitre.app" })).toBeNull()
    expect(parseCreativeStateParam("nope", { hostname: "localhost" })).toBeNull()
  })
})
