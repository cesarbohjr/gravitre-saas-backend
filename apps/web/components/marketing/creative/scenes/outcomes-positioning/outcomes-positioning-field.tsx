"use client"

import { useEffect, useRef, useState } from "react"
import Link from "next/link"
import { NucleoSuccess } from "@/components/icons/nucleo/semantic"
import { cn } from "@/lib/utils"
import { GravitreEvidenceMark } from "../../primitives/evidence-mark"
import { withCreativeScene } from "../../fallbacks/with-creative-scene"
import { useCreativePerformance } from "../../core/use-creative-performance"
import {
  ILLUSTRATIVE_CONTEXT,
  OUTCOME_CATEGORIES,
  OUTCOMES_COLLAPSE_PATH_ID,
  PHASE_CAPTION,
  nextPhase,
  parseOutcomesStateParam,
  showCategories,
  showCluster,
  showEvidence,
  showTraces,
  type OutcomesPhase,
} from "./storyboard"

function ReducedModel() {
  return (
    <div className="space-y-3 text-sm text-[color:var(--g-text-secondary)]">
      <p className="font-medium">Context</p>
      <p>{ILLUSTRATIVE_CONTEXT}</p>
      <p className="font-medium">Categories</p>
      <p>{OUTCOME_CATEGORIES.map((c) => c.label).join(" · ")}</p>
      <GravitreEvidenceMark label="Categories only" />
      <p className="text-[11px] text-[color:var(--g-text-muted)]">No invented metrics.</p>
    </div>
  )
}

function TraceThreads({ clustered }: { clustered: boolean }) {
  const paths = [
    { d: "M 20 30 Q 80 10 140 40", y: 0 },
    { d: "M 20 50 Q 90 55 140 50", y: 1 },
    { d: "M 20 70 Q 70 90 140 60", y: 2 },
  ]
  return (
    <svg
      viewBox="0 0 160 90"
      className="pointer-events-none mx-auto h-20 w-48"
      aria-hidden
      data-testid="outcomes-traces"
    >
      {paths.map((p, i) => (
        <path
          key={i}
          d={clustered ? "M 20 50 Q 80 50 140 50" : p.d}
          fill="none"
          stroke="#16a374"
          strokeWidth="2"
          strokeLinecap="round"
          opacity={0.55 + i * 0.12}
        />
      ))}
    </svg>
  )
}

function OutcomesPositioningFieldImpl({ className }: { className?: string }) {
  const rootRef = useRef<HTMLDivElement>(null)
  const { reducedMotion: reduced, shouldAnimate, quality } = useCreativePerformance(rootRef)
  const [frozenPhase, setFrozenPhase] = useState<OutcomesPhase | null>(null)
  const [phase, setPhase] = useState<OutcomesPhase>("quiet")

  useEffect(() => {
    if (typeof window === "undefined") return
    const frozen = parseOutcomesStateParam(
      new URLSearchParams(window.location.search).get("outcomesState"),
      { hostname: window.location.hostname },
    )
    setFrozenPhase(frozen)
    if (frozen) setPhase(frozen)
  }, [])

  useEffect(() => {
    if (frozenPhase || !shouldAnimate) return
    const t = window.setTimeout(() => setPhase((p) => nextPhase(p)), 1100)
    return () => window.clearTimeout(t)
  }, [phase, shouldAnimate, frozenPhase])

  const traces = showTraces(phase)
  const cluster = showCluster(phase)
  const categories = showCategories(phase)
  const evidence = showEvidence(phase)

  return (
    <div
      ref={rootRef}
      className={cn("mx-auto w-full max-w-3xl", className)}
      data-testid="outcomes-positioning-field"
      data-creative-phase={phase}
      data-creative-frozen={frozenPhase ? "1" : "0"}
      data-creative-quality={quality}
      data-outcomes-path-id={
        ["categories", "evidence", "honest"].includes(phase) ? OUTCOMES_COLLAPSE_PATH_ID : undefined
      }
    >
      {reduced ? (
        <div className="rounded-2xl border border-divide bg-white p-5" data-testid="outcomes-reduced">
          <ReducedModel />
        </div>
      ) : (
        <div className="rounded-2xl border border-divide bg-white p-4 md:p-6" data-testid="outcomes-desktop">
          <p className="text-center text-sm text-[color:var(--g-text-secondary)]">{ILLUSTRATIVE_CONTEXT}</p>

          {traces ? (
            <div className="mt-4">
              <TraceThreads clustered={cluster} />
            </div>
          ) : null}

          {categories ? (
            <div
              className="mt-5 flex flex-wrap items-center justify-center gap-2 md:gap-3"
              data-testid="outcomes-categories"
            >
              {OUTCOME_CATEGORIES.map((cat) => (
                <div
                  key={cat.id}
                  className="min-w-[5.5rem] rounded-xl border border-[color:var(--color-brand,#16a374)] px-3 py-2.5 text-center"
                  data-testid={`outcomes-cat-${cat.id}`}
                >
                  <p className="text-[11px] font-semibold text-[color:var(--g-text-secondary)]">{cat.label}</p>
                  <p className="mt-0.5 text-[10px] text-[color:var(--g-text-muted)]">category</p>
                </div>
              ))}
            </div>
          ) : null}

          {evidence ? (
            <div className="mt-4 flex flex-col items-center gap-1" data-testid="outcomes-evidence">
              <GravitreEvidenceMark label="Verified run traces" />
              <GravitreEvidenceMark label="No invented dollar claims" />
            </div>
          ) : null}
        </div>
      )}

      <p className="mt-3 text-center text-sm font-medium text-[color:var(--g-text-secondary)]" aria-live="polite">
        {reduced ? "Illustrative outcomes positioning." : PHASE_CAPTION[phase]}
      </p>
      <p className="mt-2 flex items-center justify-center gap-1 text-center text-[11px] text-[color:var(--g-text-muted)]">
        <NucleoSuccess className="h-3 w-3" aria-hidden />
        Illustrative outcomes positioning — categories only. No invented metrics.
      </p>
      <p className="mt-2 text-center text-[11px] text-[color:var(--g-text-muted)]">
        <Link className="underline underline-offset-2" href="/docs/guides/how-to/runs">
          How run activity is explained
        </Link>
      </p>
    </div>
  )
}

export const OutcomesPositioningField = withCreativeScene(
  OutcomesPositioningFieldImpl,
  "outcomes-positioning",
)
