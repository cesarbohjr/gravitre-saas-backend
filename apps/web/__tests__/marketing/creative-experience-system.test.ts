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

describe("phase 7 hardening", () => {
  it("exports creative scene fallback and brand token", async () => {
    const { CREATIVE_BRAND, CreativeSceneFallback } = await import("@/components/marketing/creative")
    expect(CREATIVE_BRAND).toBe("#16a374")
    expect(CreativeSceneFallback).toBeTypeOf("function")
  })
})

describe("phase 8 GIBE learning loop storyboard", () => {
  it("follows ACTION → OBSERVE → EVALUATE → RECOMMEND → APPROVE → RETAIN", async () => {
    const {
      PHASE_ORDER,
      LOOP_STAGES,
      nextPhase,
      isWaiting,
      isAdvisory,
      GIBE_PREFERENCE_PATH_ID,
      activeStageIds,
    } = await import("@/components/marketing/creative/scenes/gibe-learning/storyboard")
    expect(LOOP_STAGES.map((s) => s.id)).toEqual([
      "action",
      "observe",
      "evaluate",
      "recommend",
      "approve",
      "retain",
    ])
    expect(PHASE_ORDER).toContain("recommend")
    expect(isAdvisory("recommend")).toBe(true)
    expect(isWaiting("approve")).toBe(true)
    expect(nextPhase("approve")).toBe("retain")
    expect(activeStageIds("retain")).toContain("approve")
    expect(GIBE_PREFERENCE_PATH_ID).toBe("path-gibe-prefer")
  })

  it("parses gibeState only on local hosts", async () => {
    const { parseGibeStateParam } = await import(
      "@/components/marketing/creative/scenes/gibe-learning/storyboard"
    )
    expect(parseGibeStateParam("approve", { hostname: "localhost" })).toBe("approve")
    expect(parseGibeStateParam("approve", { hostname: "gravitre.app" })).toBeNull()
  })
})

describe("phase 9 voice intent storyboard", () => {
  it("follows Waveform → structure → intent → context → action → response", async () => {
    const {
      PHASE_ORDER,
      VOICE_STAGES,
      nextPhase,
      showStructure,
      VOICE_TURN_PATH_ID,
      activeStageIds,
    } = await import("@/components/marketing/creative/scenes/voice-intent/storyboard")
    expect(VOICE_STAGES.map((s) => s.id)).toEqual([
      "waveform",
      "structure",
      "intent",
      "context",
      "action",
      "response",
    ])
    expect(PHASE_ORDER).toContain("waveform")
    expect(showStructure("structure")).toBe(true)
    expect(nextPhase("action")).toBe("response")
    expect(activeStageIds("response")).toContain("action")
    expect(VOICE_TURN_PATH_ID).toBe("path-voice-turn")
  })

  it("parses voiceState only on local hosts", async () => {
    const { parseVoiceStateParam } = await import(
      "@/components/marketing/creative/scenes/voice-intent/storyboard"
    )
    expect(parseVoiceStateParam("action", { hostname: "localhost" })).toBe("action")
    expect(parseVoiceStateParam("action", { hostname: "gravitre.app" })).toBeNull()
  })
})

describe("phase 10 outcomes positioning storyboard", () => {
  it("collapses traces into revenue / retention / efficiency without metrics", async () => {
    const {
      PHASE_ORDER,
      OUTCOME_CATEGORIES,
      nextPhase,
      showCategories,
      OUTCOMES_COLLAPSE_PATH_ID,
    } = await import("@/components/marketing/creative/scenes/outcomes-positioning/storyboard")
    expect(OUTCOME_CATEGORIES.map((c) => c.id)).toEqual(["revenue", "retention", "efficiency"])
    expect(PHASE_ORDER).toEqual(["quiet", "traces", "cluster", "categories", "evidence", "honest"])
    expect(showCategories("categories")).toBe(true)
    expect(nextPhase("categories")).toBe("evidence")
    expect(OUTCOMES_COLLAPSE_PATH_ID).toBe("path-outcomes-collapse")
  })

  it("parses outcomesState only on local hosts", async () => {
    const { parseOutcomesStateParam } = await import(
      "@/components/marketing/creative/scenes/outcomes-positioning/storyboard"
    )
    expect(parseOutcomesStateParam("categories", { hostname: "localhost" })).toBe("categories")
    expect(parseOutcomesStateParam("categories", { hostname: "gravitre.app" })).toBeNull()
  })
})

describe("phase 11 creative performance", () => {
  it("resolves quality tiers including medium and fallback", async () => {
    const { resolveCreativeQuality, creativeDprCap, shouldRunCreativeAnimation } = await import(
      "@/components/marketing/creative/core/performance-manager"
    )
    expect(resolveCreativeQuality({ reducedMotion: true })).toBe("fallback")
    expect(resolveCreativeQuality({ preferLow: true })).toBe("low")
    expect(resolveCreativeQuality({ preferMedium: true })).toBe("medium")
    expect(resolveCreativeQuality({})).toBe("high")
    expect(creativeDprCap("medium")).toBe(1.5)
    expect(shouldRunCreativeAnimation({ reducedMotion: false, visible: true, documentHidden: true })).toBe(
      false,
    )
  })
})

describe("CES 2.0 scene controller", () => {
  it("keeps selection independent of narrative progression", async () => {
    const {
      createSceneControllerState,
      reduceSceneController,
    } = await import("@/components/marketing/creative/core/scene-controller")
    const beats = ["sources", "normalize", "match"] as const
    let state = createSceneControllerState(beats, { mode: "stepped" })
    state = reduceSceneController(state, { type: "stepForward" })
    expect(state.beat).toBe("normalize")
    state = reduceSceneController(state, { type: "selectObject", id: "m1" })
    expect(state.selectedObjectId).toBe("m1")
    expect(state.beat).toBe("normalize")
    state = reduceSceneController(state, { type: "stepForward" })
    expect(state.beat).toBe("match")
    expect(state.selectedObjectId).toBe("m1")
    state = reduceSceneController(state, { type: "replay" })
    expect(state.beatIndex).toBe(0)
    expect(state.selectedObjectId).toBe("m1")
    state = reduceSceneController(state, { type: "reset" })
    expect(state.selectedObjectId).toBeNull()
  })
})

describe("CES 2.0 KF-A normalize (decision A)", () => {
  it("shares deterministic normalize across fixtures and display", async () => {
    const {
      normalizeIllustrativeMention,
      KF_A_MENTIONS,
      mentionWithNormalized,
    } = await import("@/components/marketing/creative/scenes/knowledge-fabric/normalize")
    expect(normalizeIllustrativeMention("Acme Corp")).toBe("acme corp")
    expect(normalizeIllustrativeMention("acme corp.")).toBe("acme corp")
    expect(normalizeIllustrativeMention("Sarah")).toBe("sarah")
    expect(normalizeIllustrativeMention("Sarah Smith")).toBe("sarah smith")
    const views = KF_A_MENTIONS.map(mentionWithNormalized)
    const acme = views.filter((m) => m.entityKey === "acme-corp")
    expect(acme).toHaveLength(2)
    expect(acme[0]?.normalized).toBe(acme[1]?.normalized)
    const people = views.filter((m) => m.fuzzyPersonDemo)
    expect(people[0]?.normalized).not.toBe(people[1]?.normalized)
  })

  it("exposes KF-A beat order for stepped mode", async () => {
    const { KF_A_BEATS } = await import(
      "@/components/marketing/creative/scenes/knowledge-fabric/entity-convergence-workbench"
    )
    expect([...KF_A_BEATS]).toEqual([
      "sources",
      "normalize",
      "match",
      "resolve",
      "evidence",
      "reject",
      "compare",
    ])
  })
})

describe("CES 2.0 Pilot 1 mobile topology", () => {
  it("does not use ring-spin in mobile core", async () => {
    const { readFileSync } = await import("node:fs")
    const { resolve } = await import("node:path")
    const src = readFileSync(
      resolve(
        process.cwd(),
        "components/marketing/system/department-network/department-network-mobile.tsx",
      ),
      "utf8",
    )
    expect(src).toMatch(/topologyForCoreState/)
    expect(src).toMatch(/mobile-topology-svg/)
    expect(src).not.toMatch(/animate-spin/)
  })
})

describe("CES 2.0 KF-A single field (visual approval)", () => {
  it("is a single structured field without chip-column layout", async () => {
    const { readFileSync } = await import("node:fs")
    const { resolve } = await import("node:path")
    const src = readFileSync(
      resolve(
        process.cwd(),
        "components/marketing/creative/scenes/knowledge-fabric/entity-convergence-workbench.tsx",
      ),
      "utf8",
    )
    expect(src).toMatch(/data-single-field="1"/)
    expect(src).toMatch(/data-testid="kf-a-field"/)
    expect(src).toMatch(/kf-a-compare-lens/)
    expect(src).not.toMatch(/permanent instructional sidebar/i)
  })
})

describe("CES 2.0 product doc links", () => {
  it("connects orchestration and governance scenes to existing docs", async () => {
    const { readFileSync } = await import("node:fs")
    const { resolve } = await import("node:path")
    const orchestration = readFileSync(
      resolve(process.cwd(), "components/marketing/creative/scenes/agent-orchestration/orchestration-field.tsx"),
      "utf8",
    )
    const governed = readFileSync(
      resolve(process.cwd(), "components/marketing/creative/scenes/governed-execution/governed-execution-field.tsx"),
      "utf8",
    )
    expect(orchestration).toMatch(/\/docs\/guides\/how-to\/agents/)
    expect(orchestration).toMatch(/\/docs\/guides\/how-to\/approvals/)
    expect(governed).toMatch(/\/docs\/guides\/how-to\/approvals/)
    expect(orchestration).toMatch(/Failure path/)
  })
})
