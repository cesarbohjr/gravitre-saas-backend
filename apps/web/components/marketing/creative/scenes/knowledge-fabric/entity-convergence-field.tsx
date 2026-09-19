"use client"

import { useEffect, useRef, useState } from "react"
import { useInView, useReducedMotion } from "framer-motion"
import { NucleoIntelligence, NucleoSuccess } from "@/components/icons/nucleo/semantic"
import { cn } from "@/lib/utils"
import { GravitreEvidenceMark } from "../../primitives/evidence-mark"
import {
  ILLUSTRATIVE_CONTEXT,
  MENTIONS,
  PHASE_CAPTION,
  convergingMentionIds,
  nextPhase,
  parseKfStateParam,
  resolvedEntityLabel,
  showEvidence,
  showFuzzyReject,
  showNormalized,
  showPersistEdge,
  type FabricPhase,
} from "./storyboard"

function MentionChip({
  raw,
  normalized,
  showNorm,
  converging,
  rejected,
}: {
  raw: string
  normalized: string
  showNorm: boolean
  converging?: boolean
  rejected?: boolean
}) {
  return (
    <div
      className={cn(
        "rounded-lg border px-2.5 py-1.5 text-left shadow-sm",
        converging && "border-[color:var(--color-brand,#16a374)] bg-[color:color-mix(in_srgb,var(--color-brand,#16a374)_8%,white)]",
        rejected && "border-divide opacity-90",
        !converging && !rejected && "border-divide bg-white",
      )}
      data-converging={converging ? "1" : "0"}
      data-fuzzy-reject={rejected ? "1" : "0"}
    >
      <p className="text-xs font-semibold text-[color:var(--g-text-secondary)]">{raw}</p>
      {showNorm ? (
        <p className="mt-0.5 font-mono text-[10px] text-[color:var(--g-text-muted)]">→ {normalized}</p>
      ) : null}
    </div>
  )
}

function ReducedModel() {
  return (
    <div className="space-y-3 text-sm text-[color:var(--g-text-secondary)]">
      <p className="font-medium">Context</p>
      <p>{ILLUSTRATIVE_CONTEXT}</p>
      <p className="font-medium">Exact match</p>
      <p>
        <span className="font-semibold">Acme Corp</span> + <span className="font-semibold">acme corp.</span> → one
        entity after normalize.
      </p>
      <p className="font-medium">Not fuzzy</p>
      <p>
        <span className="font-semibold">Sarah</span> and <span className="font-semibold">Sarah Smith</span> stay
        separate.
      </p>
      <GravitreEvidenceMark label="Exact normalized match" />
      <p className="pt-1 text-[11px] text-[color:var(--g-text-muted)]">
        Knowledge Fabric ≠ org graph. Not a live run.
      </p>
    </div>
  )
}

export function EntityConvergenceField({ className }: { className?: string }) {
  const reducePreference = useReducedMotion()
  const [mounted, setMounted] = useState(false)
  useEffect(() => setMounted(true), [])
  const reduced = mounted && !!reducePreference

  const rootRef = useRef<HTMLDivElement>(null)
  const inView = useInView(rootRef, { amount: 0.25, once: false })
  const [hidden, setHidden] = useState(false)
  const [frozenPhase, setFrozenPhase] = useState<FabricPhase | null>(null)
  const [phase, setPhase] = useState<FabricPhase>("quiet")

  useEffect(() => {
    const onVis = () => setHidden(document.hidden)
    onVis()
    document.addEventListener("visibilitychange", onVis)
    return () => document.removeEventListener("visibilitychange", onVis)
  }, [])

  useEffect(() => {
    if (typeof window === "undefined") return
    const params = new URLSearchParams(window.location.search)
    const frozen = parseKfStateParam(params.get("kfState"), { hostname: window.location.hostname })
    setFrozenPhase(frozen)
    if (frozen) setPhase(frozen)
  }, [])

  useEffect(() => {
    if (frozenPhase || reduced || !inView || hidden) return
    const t = window.setTimeout(() => setPhase((p) => nextPhase(p)), 1200)
    return () => window.clearTimeout(t)
  }, [phase, reduced, inView, hidden, frozenPhase])

  const converging = new Set(convergingMentionIds(phase))
  const entityLabel = resolvedEntityLabel(phase)
  const fuzzy = showFuzzyReject(phase)
  const evidence = showEvidence(phase)
  const persist = showPersistEdge(phase)
  const showNorm = showNormalized(phase)

  return (
    <div
      ref={rootRef}
      className={cn("mx-auto w-full max-w-4xl", className)}
      data-testid="entity-convergence-field"
      data-creative-phase={phase}
      data-creative-frozen={frozenPhase ? "1" : "0"}
      data-kf-exact-converged={entityLabel ? "1" : "0"}
      data-kf-fuzzy-merged="0"
    >
      {reduced ? (
        <div className="rounded-2xl border border-divide bg-white p-5" data-testid="kf-reduced">
          <ReducedModel />
        </div>
      ) : (
        <>
          <div
            className="hidden rounded-2xl border border-divide bg-white p-4 md:block md:p-6"
            data-testid="kf-desktop"
          >
            <div className="grid grid-cols-[1.2fr_1fr_1.1fr] gap-4">
              <div>
                <p className="text-[10px] font-semibold uppercase tracking-wide text-[color:var(--g-text-muted)]">
                  Mentions
                </p>
                <div className="mt-2 flex flex-col gap-2">
                  {MENTIONS.map((m) => (
                    <MentionChip
                      key={m.id}
                      raw={m.raw}
                      normalized={m.normalized}
                      showNorm={showNorm}
                      converging={converging.has(m.id)}
                      rejected={fuzzy && !!m.fuzzyPersonDemo}
                    />
                  ))}
                </div>
              </div>

              <div className="flex flex-col items-center justify-center text-center">
                <NucleoIntelligence className="h-6 w-6 text-[color:var(--g-intelligence)]" aria-hidden />
                <p className="mt-2 text-[10px] font-semibold uppercase tracking-wide text-[color:var(--g-text-muted)]">
                  Match gate
                </p>
                <p className="mt-1 text-xs text-[color:var(--g-text-secondary)]">
                  {phase === "quiet" || phase === "receive"
                    ? "Waiting for mentions"
                    : phase === "normalize"
                      ? "Normalize"
                      : "Exact after normalize"}
                </p>
                {persist ? (
                  <svg viewBox="0 0 80 12" className="mt-3 w-24" aria-hidden data-testid="kf-persist-edge">
                    <line
                      x1="4"
                      y1="6"
                      x2="76"
                      y2="6"
                      stroke="#16a374"
                      strokeWidth="2"
                      strokeLinecap="round"
                    />
                  </svg>
                ) : null}
              </div>

              <div>
                <p className="text-[10px] font-semibold uppercase tracking-wide text-[color:var(--g-text-muted)]">
                  Resolved
                </p>
                {entityLabel ? (
                  <div
                    className="mt-2 rounded-xl border border-[color:var(--color-brand,#16a374)] bg-white px-3 py-2"
                    data-testid="kf-resolved-entity"
                  >
                    <p className="text-sm font-semibold text-[color:var(--color-brand,#16a374)]">{entityLabel}</p>
                    <p className="text-[10px] text-[color:var(--g-text-muted)]">Exact normalized identity</p>
                  </div>
                ) : (
                  <p className="mt-2 text-sm text-[color:var(--g-text-muted)]">No entity yet.</p>
                )}
                {fuzzy ? (
                  <div className="mt-3 space-y-1.5" data-testid="kf-fuzzy-kept-apart">
                    <p className="text-[10px] font-semibold uppercase tracking-wide text-amber-800">
                      Kept separate
                    </p>
                    <MentionChip raw="Sarah" normalized="sarah" showNorm rejected />
                    <MentionChip raw="Sarah Smith" normalized="sarah smith" showNorm rejected />
                  </div>
                ) : null}
                {evidence ? (
                  <div className="mt-3 flex flex-col gap-1" data-testid="kf-evidence">
                    <GravitreEvidenceMark label="Exact normalized match" />
                    <GravitreEvidenceMark label="Sources: CRM · email" />
                  </div>
                ) : null}
              </div>
            </div>
          </div>

          <div
            className="space-y-3 rounded-2xl border border-divide bg-white p-4 md:hidden"
            data-testid="kf-mobile"
          >
            <p className="text-sm font-medium">{ILLUSTRATIVE_CONTEXT}</p>
            <div className="flex flex-col gap-2">
              {MENTIONS.map((m) => (
                <MentionChip
                  key={m.id}
                  raw={m.raw}
                  normalized={m.normalized}
                  showNorm={showNorm}
                  converging={converging.has(m.id)}
                  rejected={fuzzy && !!m.fuzzyPersonDemo}
                />
              ))}
            </div>
            {entityLabel ? (
              <p className="text-sm font-semibold text-[color:var(--color-brand,#16a374)]" data-testid="kf-resolved-entity">
                Resolved: {entityLabel}
              </p>
            ) : null}
            {evidence ? (
              <div data-testid="kf-evidence">
                <GravitreEvidenceMark label="Exact normalized match" />
              </div>
            ) : null}
          </div>
        </>
      )}

      <p className="mt-3 text-center text-sm font-medium text-[color:var(--g-text-secondary)]" aria-live="polite">
        {reduced ? "Illustrative entity convergence model." : PHASE_CAPTION[phase]}
      </p>
      <p className="mt-2 flex items-center justify-center gap-1 text-center text-[11px] text-[color:var(--g-text-muted)]">
        <NucleoSuccess className="h-3 w-3" aria-hidden />
        Illustrative entity convergence — exact and normalized mention match. Not fuzzy person matching. Not a live
        org graph.
      </p>
    </div>
  )
}
