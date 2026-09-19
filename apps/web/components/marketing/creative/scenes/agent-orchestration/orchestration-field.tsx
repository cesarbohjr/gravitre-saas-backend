"use client"

import { useEffect, useRef, useState } from "react"
import { useInView, useReducedMotion } from "framer-motion"
import {
  NucleoChat,
  NucleoError,
  NucleoIntelligence,
  NucleoRun,
  NucleoSearch,
  NucleoSuccess,
} from "@/components/icons/nucleo/semantic"
import { cn } from "@/lib/utils"
import { GravitreAgentNode } from "../../primitives/agent-node"
import { GravitreEvidenceMark } from "../../primitives/evidence-mark"
import { topologyForCoreState } from "../../primitives/relational-topology"
import type { CoreState } from "@/components/marketing/system/department-network/types"
import {
  AGENT_ROLES,
  ILLUSTRATIVE_REQUEST,
  PHASE_CAPTION,
  PLAN_CHIPS,
  TOOLS,
  nextPhase,
  type OrchestrationPhase,
} from "./storyboard"

const ROLE_ICONS = {
  research: NucleoSearch,
  analysis: NucleoIntelligence,
  support: NucleoChat,
  ops: NucleoRun,
} as const

function coreStateFor(phase: OrchestrationPhase): CoreState {
  switch (phase) {
    case "intent":
      return "receiving"
    case "understand":
      return "connecting"
    case "plan":
    case "delegate":
      return "coordinating"
    case "waiting":
      return "verifying"
    case "verify":
    case "outcome":
    case "learned":
      return "learned"
    case "failure":
      return "verifying"
    default:
      return "idle"
  }
}

function MiniTopology({ phase }: { phase: OrchestrationPhase }) {
  const layout = topologyForCoreState(coreStateFor(phase))
  return (
    <svg viewBox="0 0 80 72" className="h-24 w-28" aria-hidden>
      {layout.edges.map(([a, b], i) => {
        const pa = layout.nodes[a]
        const pb = layout.nodes[b]
        if (!pa || !pb) return null
        return (
          <line
            key={i}
            x1={pa.x}
            y1={pa.y}
            x2={pb.x}
            y2={pb.y}
            stroke="color-mix(in srgb, var(--g-intelligence) 40%, #c5c9d0)"
            strokeWidth={1.1}
          />
        )
      })}
      {layout.nodes.map((p, i) => (
        <circle key={i} cx={p.x} cy={p.y} r={i === 0 ? 4.5 : 2.4} fill={i === 0 ? "#16a374" : "#8b93a0"} />
      ))}
    </svg>
  )
}

function ReducedModel() {
  return (
    <div className="space-y-3 text-sm text-[color:var(--g-text-secondary)]">
      <p className="font-medium">Intent</p>
      <p>{ILLUSTRATIVE_REQUEST}</p>
      <p className="font-medium">Plan</p>
      <ul className="list-disc pl-5">
        {PLAN_CHIPS.map((c) => (
          <li key={c}>{c}</li>
        ))}
      </ul>
      <p className="font-medium">Capabilities</p>
      <p>{AGENT_ROLES.map((a) => a.label).join(" · ")}</p>
      <p className="font-medium">Systems</p>
      <p>{TOOLS.join(" · ")}</p>
      <p className="font-medium">Verification</p>
      <GravitreEvidenceMark label="Sources + run outcome" />
      <p className="pt-1 font-medium text-[color:var(--color-brand,#16a374)]">
        Outcome: at-risk accounts identified; follow-up prepared after approval.
      </p>
    </div>
  )
}

export function AgentOrchestrationField({ className }: { className?: string }) {
  const reducePreference = useReducedMotion()
  const [mounted, setMounted] = useState(false)
  useEffect(() => setMounted(true), [])
  const reduced = mounted && !!reducePreference

  const rootRef = useRef<HTMLDivElement>(null)
  const inView = useInView(rootRef, { amount: 0.25, once: false })
  const [hidden, setHidden] = useState(false)
  const [phase, setPhase] = useState<OrchestrationPhase>("quiet")
  const [mode, setMode] = useState<"success" | "failure">("success")

  useEffect(() => {
    const onVis = () => setHidden(document.hidden)
    onVis()
    document.addEventListener("visibilitychange", onVis)
    return () => document.removeEventListener("visibilitychange", onVis)
  }, [])

  useEffect(() => {
    if (reduced || !inView || hidden) return
    const t = window.setTimeout(() => setPhase((p) => nextPhase(p, mode)), phase === "waiting" ? 1600 : 1100)
    return () => window.clearTimeout(t)
  }, [phase, reduced, inView, hidden, mode])

  const showPlan = ["plan", "delegate", "tools", "parallel", "waiting", "verify", "outcome", "learned", "failure"].includes(phase)
  const showAgents = ["delegate", "tools", "parallel", "waiting", "verify", "outcome", "learned", "failure"].includes(phase)
  const showTools = ["tools", "parallel", "waiting", "verify", "outcome", "learned", "failure"].includes(phase)
  const waiting = phase === "waiting"
  const failed = phase === "failure"

  return (
    <div ref={rootRef} className={cn("mx-auto w-full max-w-4xl", className)}>
      {reduced ? (
        <div className="rounded-2xl border border-divide bg-white p-5">
          <ReducedModel />
        </div>
      ) : (
        <>
          <div className="hidden rounded-2xl border border-divide bg-white p-4 md:block md:p-6">
            <div className="grid grid-cols-[1.1fr_1.4fr_1fr] gap-4">
              <div>
                <p className="text-[10px] font-semibold uppercase tracking-wide text-[color:var(--g-text-muted)]">Intent</p>
                <p className="mt-2 text-sm font-medium leading-snug text-[color:var(--g-text-secondary)]">{ILLUSTRATIVE_REQUEST}</p>
              </div>
              <div className="flex flex-col items-center">
                <MiniTopology phase={phase} />
                {showPlan ? (
                  <ul className="mt-2 flex flex-wrap justify-center gap-1">
                    {PLAN_CHIPS.map((c) => (
                      <li key={c} className="rounded-md border border-divide px-1.5 py-0.5 text-[10px] text-[color:var(--g-text-secondary)]">
                        {c}
                      </li>
                    ))}
                  </ul>
                ) : null}
              </div>
              <div>
                <p className="text-[10px] font-semibold uppercase tracking-wide text-[color:var(--g-text-muted)]">Outcome</p>
                {phase === "outcome" || phase === "learned" || phase === "verify" ? (
                  <p className="mt-2 text-sm font-medium text-[color:var(--color-brand,#16a374)]">
                    Follow-up prepared for at-risk accounts.
                  </p>
                ) : (
                  <p className="mt-2 text-sm text-[color:var(--g-text-muted)]">Resolves after verification.</p>
                )}
                {(phase === "verify" || phase === "outcome" || phase === "learned") && (
                  <div className="mt-2 flex flex-col gap-1">
                    <GravitreEvidenceMark label="Sources" />
                    <GravitreEvidenceMark label="Run outcome" />
                  </div>
                )}
                {waiting ? <div className="mt-2"><GravitreEvidenceMark label="Needs approval" tone="waiting" /></div> : null}
                {failed ? <div className="mt-2"><GravitreEvidenceMark label="Send failed" tone="error" /></div> : null}
              </div>
            </div>
            {showAgents ? (
              <div className="mt-4 flex flex-wrap justify-center gap-2">
                {AGENT_ROLES.map((role) => (
                  <GravitreAgentNode
                    key={role.id}
                    label={role.label}
                    icon={ROLE_ICONS[role.id]}
                    active={showAgents}
                    waiting={waiting && role.id === "ops"}
                    failed={failed && role.id === "support"}
                  />
                ))}
              </div>
            ) : null}
            {showTools ? (
              <p className="mt-3 text-center text-[11px] text-[color:var(--g-text-muted)]">
                Systems: {TOOLS.join(" · ")}
                {phase === "parallel" ? " — two paths in parallel." : ""}
                {waiting ? " — write path paused." : ""}
                {failed ? " — messaging blocked; research remains." : ""}
              </p>
            ) : null}
          </div>

          <div className="space-y-3 rounded-2xl border border-divide bg-white p-4 md:hidden">
            <p className="text-sm font-medium">{ILLUSTRATIVE_REQUEST}</p>
            <MiniTopology phase={phase} />
            {showPlan ? (
              <ul className="space-y-1 text-xs text-[color:var(--g-text-secondary)]">
                {PLAN_CHIPS.map((c) => (
                  <li key={c}>{c}</li>
                ))}
              </ul>
            ) : null}
            {showAgents ? (
              <div className="flex flex-col gap-2">
                {AGENT_ROLES.map((role) => (
                  <GravitreAgentNode
                    key={role.id}
                    label={role.label}
                    icon={ROLE_ICONS[role.id]}
                    active
                    waiting={waiting && role.id === "ops"}
                    failed={failed && role.id === "support"}
                  />
                ))}
              </div>
            ) : null}
            {(phase === "verify" || phase === "outcome" || phase === "learned") && (
              <GravitreEvidenceMark label="Sources + run outcome" />
            )}
          </div>
        </>
      )}

      <p className="mt-3 text-center text-sm font-medium text-[color:var(--g-text-secondary)]" aria-live="polite">
        {reduced ? "Illustrative orchestration model." : PHASE_CAPTION[phase]}
      </p>
      <div className="mt-2 flex justify-center gap-2">
        <button
          type="button"
          className={cn("rounded-md border px-2 py-1 text-[11px]", mode === "success" ? "border-brand text-brand" : "border-divide")}
          onClick={() => {
            setMode("success")
            setPhase("quiet")
          }}
        >
          Success path
        </button>
        <button
          type="button"
          className={cn("rounded-md border px-2 py-1 text-[11px]", mode === "failure" ? "border-red-400 text-red-700" : "border-divide")}
          onClick={() => {
            setMode("failure")
            setPhase("parallel")
          }}
        >
          Failure path
        </button>
      </div>
      <p className="mt-2 flex items-center justify-center gap-1 text-center text-[11px] text-[color:var(--g-text-muted)]">
        {failed ? <NucleoError className="h-3 w-3" aria-hidden /> : <NucleoSuccess className="h-3 w-3" aria-hidden />}
        Illustrative orchestration — not a live run. Governance pauses writes; learning is advisory.
      </p>
    </div>
  )
}
