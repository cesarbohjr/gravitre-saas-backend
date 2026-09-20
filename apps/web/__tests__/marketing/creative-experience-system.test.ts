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

describe("pilot 3 knowledge fabric storyboard", () => {
  it("keeps beat order and converges only exact normalized pairs", async () => {
    const {
      PHASE_ORDER,
      convergingMentionIds,
      resolvedEntityLabel,
      showFuzzyReject,
      nextPhase,
    } = await import("@/components/marketing/creative/scenes/knowledge-fabric/storyboard")
    expect(PHASE_ORDER[0]).toBe("quiet")
    expect(PHASE_ORDER).toContain("match")
    expect(PHASE_ORDER).toContain("reject_fuzzy")
    expect(convergingMentionIds("match")).toEqual(["m1", "m2"])
    expect(resolvedEntityLabel("match")).toBe("Acme Corp")
    expect(showFuzzyReject("reject_fuzzy")).toBe(true)
    expect(nextPhase("match")).toBe("reject_fuzzy")
  })

  it("never reports fuzzy person merge", async () => {
    const { MENTIONS, convergingMentionIds, PHASE_ORDER } = await import(
      "@/components/marketing/creative/scenes/knowledge-fabric/storyboard"
    )
    const fuzzyIds = MENTIONS.filter((m) => m.fuzzyPersonDemo).map((m) => m.id)
    expect(fuzzyIds).toEqual(["m3", "m4"])
    for (const phase of PHASE_ORDER) {
      const converged = convergingMentionIds(phase)
      expect(converged.some((id) => fuzzyIds.includes(id))).toBe(false)
    }
  })

  it("parses kfState only on local hosts", async () => {
    const { parseKfStateParam } = await import(
      "@/components/marketing/creative/scenes/knowledge-fabric/storyboard"
    )
    expect(parseKfStateParam("match", { hostname: "localhost" })).toBe("match")
    expect(parseKfStateParam("reject_fuzzy", { hostname: "127.0.0.1" })).toBe("reject_fuzzy")
    expect(parseKfStateParam("match", { hostname: "gravitre.app" })).toBeNull()
    expect(parseKfStateParam("verify", { hostname: "localhost" })).toBeNull()
  })
})

describe("phase 7 connector fabric storyboard", () => {
  it("uses capability ports and pauses WRITE for approval", async () => {
    const { PHASE_ORDER, CAPABILITY_PORTS, writeWaiting, nextPhase } = await import(
      "@/components/marketing/creative/scenes/connector-fabric/storyboard"
    )
    expect(PHASE_ORDER).toContain("write_waiting")
    expect(CAPABILITY_PORTS.every((p) => p.caps.length > 0)).toBe(true)
    expect(writeWaiting("write_waiting")).toBe(true)
    expect(nextPhase("write_waiting")).toBe("execute")
  })

  it("parses cfState only on local hosts", async () => {
    const { parseCfStateParam } = await import(
      "@/components/marketing/creative/scenes/connector-fabric/storyboard"
    )
    expect(parseCfStateParam("write_waiting", { hostname: "localhost" })).toBe("write_waiting")
    expect(parseCfStateParam("write_waiting", { hostname: "gravitre.app" })).toBeNull()
  })
})

describe("phase 7 governed execution storyboard", () => {
  it("follows POLICY → RISK → APPROVAL → EXECUTE → EVIDENCE and keeps path id", async () => {
    const {
      PHASE_ORDER,
      GATE_STAGES,
      nextPhase,
      isWaiting,
      GOVERNED_WRITE_PATH_ID,
      activeStageIds,
    } = await import("@/components/marketing/creative/scenes/governed-execution/storyboard")
    expect(GATE_STAGES.map((s) => s.id)).toEqual(["policy", "risk", "approval", "execute", "evidence"])
    expect(PHASE_ORDER).toContain("approval")
    expect(isWaiting("approval")).toBe(true)
    expect(nextPhase("approval")).toBe("execute")
    expect(activeStageIds("execute")).toContain("approval")
    expect(GOVERNED_WRITE_PATH_ID).toBe("path-gov-write")
  })

  it("parses govState only on local hosts", async () => {
    const { parseGovStateParam } = await import(
      "@/components/marketing/creative/scenes/governed-execution/storyboard"
    )
    expect(parseGovStateParam("approval", { hostname: "localhost" })).toBe("approval")
    expect(parseGovStateParam("approval", { hostname: "gravitre.app" })).toBeNull()
  })
})
