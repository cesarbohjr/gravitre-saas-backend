"use client"

/**
 * CES 2.0 KF-A — Entity Convergence Workbench.
 * Production Technology scene. Exact/normalized only; Sarah stays apart.
 * The autoplay EntityConvergenceField remains available for comparison in the dev harness.
 */

import { useEffect, useMemo, useState } from "react"
import { useReducedMotion } from "framer-motion"
import { cn } from "@/lib/utils"
import { CREATIVE_TOKENS } from "../../core/tokens"
import { useSceneController } from "../../core/use-scene-controller"
import { GravitreEvidenceMark } from "../../primitives/evidence-mark"
import { withCreativeScene } from "../../fallbacks/with-creative-scene"
import {
  KF_A_MENTIONS,
  mentionWithNormalized,
  normalizeIllustrativeMention,
} from "./normalize"

export const KF_A_BEATS = [
  "sources",
  "normalize",
  "match",
  "resolve",
  "evidence",
  "reject",
  "compare",
] as const

export type KfABeat = (typeof KF_A_BEATS)[number]

/** KF-B lenses — same objects, different organization (not separate scenes). */
export type KfALens = "sources" | "normalized" | "matched" | "resolved" | "evidence" | "fragmented"

const BEAT_LABEL: Record<KfABeat, string> = {
  sources: "Sources",
  normalize: "Normalize",
  match: "Match",
  resolve: "Resolve",
  evidence: "Evidence",
  reject: "Rejected",
  compare: "Compare",
}

const BEAT_CAPTION: Record<KfABeat, string> = {
  sources: "Mentions arrive from different systems — CRM and email.",
  normalize: "Documented normalize: trim, collapse spaces, lowercase, strip trailing punctuation.",
  match: "Exact normalized string match decides convergence — not fuzzy similarity.",
  resolve: "Matching mentions converge into one resolved identity.",
  evidence: "Supporting mentions attach to the resolved identity.",
  reject: "Sarah and Sarah Smith stay separate — different normalized strings, no entity key.",
  compare: "Same field, Fragmented ↔ Resolved lens — structure stays until Replay / Reset.",
}

type MentionView = ReturnType<typeof mentionWithNormalized>

const NODE_LAYOUT: Record<string, { x: number; y: number; label: string }> = {
  m1: { x: 72, y: 78, label: "Acme Corp" },
  m2: { x: 328, y: 78, label: "acme corp." },
  m3: { x: 72, y: 168, label: "Sarah" },
  m4: { x: 328, y: 168, label: "Sarah Smith" },
}

const RESOLVE_ANCHOR = { x: 200, y: 78 }

function beatToLens(beat: KfABeat, compareResolved: boolean): KfALens {
  if (beat === "compare") return compareResolved ? "resolved" : "fragmented"
  if (beat === "sources") return "sources"
  if (beat === "normalize") return "normalized"
  if (beat === "match") return "matched"
  if (beat === "resolve" || beat === "reject") return "resolved"
  return "evidence"
}

function CompactControls({
  beat,
  beatIndex,
  total,
  onBack,
  onForward,
  onReplay,
  onReset,
}: {
  beat: KfABeat
  beatIndex: number
  total: number
  onBack: () => void
  onForward: () => void
  onReplay: () => void
  onReset: () => void
}) {
  return (
    <div
      className="flex flex-wrap items-center gap-1.5"
      role="toolbar"
      aria-label="Workbench progression"
      data-testid="kf-a-controls"
    >
      <button
        type="button"
        className="rounded-md border border-[color:var(--color-line,#eaedf1)] bg-white px-2 py-1 text-[11px] font-semibold text-[color:var(--g-text-secondary)] disabled:opacity-40"
        onClick={onBack}
        disabled={beatIndex === 0}
        aria-label="Step back"
      >
        ←
      </button>
      <span className="min-w-[6.5rem] text-center text-[11px] font-semibold text-[color:var(--color-brand,#16a374)]">
        {BEAT_LABEL[beat]}
        <span className="ml-1 font-normal text-[color:var(--g-text-muted)]">
          {beatIndex + 1}/{total}
        </span>
      </span>
      <button
        type="button"
        className="rounded-md border border-[color:var(--color-line,#eaedf1)] bg-white px-2 py-1 text-[11px] font-semibold text-[color:var(--g-text-secondary)] disabled:opacity-40"
        onClick={onForward}
        disabled={beatIndex >= total - 1}
        aria-label="Step forward"
      >
        →
      </button>
      <button
        type="button"
        className="rounded-md border border-[color:var(--color-line,#eaedf1)] bg-white px-2 py-1 text-[11px] font-medium text-[color:var(--g-text-muted)]"
        onClick={onReplay}
        aria-label="Replay from start"
      >
        Replay
      </button>
      <button
        type="button"
        className="rounded-md border border-[color:var(--color-line,#eaedf1)] bg-white px-2 py-1 text-[11px] font-medium text-[color:var(--g-text-muted)]"
        onClick={onReset}
        aria-label="Reset selection and step"
      >
        Reset
      </button>
    </div>
  )
}

export function EntityConvergenceWorkbench({ className }: { className?: string }) {
  const reducedPref = useReducedMotion()
  const reduced = !!reducedPref
  const mentions = useMemo(() => KF_A_MENTIONS.map(mentionWithNormalized), [])

  const ctrl = useSceneController(KF_A_BEATS, { mode: "stepped" })
  const {
    beat,
    beatIndex,
    selectedObjectId: selectedId,
    stepForward,
    stepBack,
    replay,
    reset,
    selectObject,
  } = ctrl

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return
      if (e.key === "ArrowRight") {
        e.preventDefault()
        stepForward()
      } else if (e.key === "ArrowLeft") {
        e.preventDefault()
        stepBack()
      } else if (e.key === "Home") {
        e.preventDefault()
        replay()
      } else if (e.key === "Escape") {
        e.preventDefault()
        selectObject(null)
      }
    }
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  }, [stepForward, stepBack, replay, selectObject])

  const selected = mentions.find((m) => m.id === selectedId) ?? null
  const [compareResolved, setCompareResolved] = useState(true)
  const lens = beatToLens(beat, compareResolved)
  const showNorm = ["normalize", "match", "resolve", "evidence", "reject", "compare"].includes(beat)
  const showMatch = ["match", "resolve", "evidence", "compare"].includes(beat)
  const showResolve = ["resolve", "evidence", "compare"].includes(beat)
  const showEvidence = beat === "evidence" || (beat === "compare" && compareResolved)
  const showReject = beat === "reject" || (beat === "compare" && !!selected?.fuzzyPersonDemo)
  const compareMode = beat === "compare"
  const fragmentedLens = compareMode && !compareResolved

  const matchGroupIds = useMemo(() => {
    if (!showMatch) return [] as string[]
    const focus = selected?.entityKey ? selected : mentions.find((m) => m.entityKey === "acme-corp")
    if (!focus?.entityKey) return []
    return mentions
      .filter((m) => m.entityKey === focus.entityKey && m.normalized === focus.normalized)
      .map((m) => m.id)
  }, [mentions, selected, showMatch])

  const matchSet = new Set(matchGroupIds)
  const canResolveAcme = matchGroupIds.length >= 2 && showResolve && !fragmentedLens
  const rejectIds = new Set(["m3", "m4"])

  function nodePosition(id: string): { x: number; y: number } {
    const base = NODE_LAYOUT[id]!
    if (canResolveAcme && matchSet.has(id) && !reduced) {
      return RESOLVE_ANCHOR
    }
    if (showReject && rejectIds.has(id) && !reduced) {
      // Spatial separation — push further apart
      return id === "m3" ? { x: 48, y: 168 } : { x: 352, y: 168 }
    }
    return { x: base.x, y: base.y }
  }

  function displayLabel(m: MentionView): string {
    if (!showNorm) return m.raw
    if (beat === "normalize" || beat === "sources") {
      return selectedId === m.id || showNorm ? m.normalized : m.raw
    }
    return showNorm ? m.normalized : m.raw
  }

  const transition = reduced ? undefined : "transition-[cx,cy,opacity,r] duration-500 ease-out"

  return (
    <div
      className={cn("mx-auto w-full max-w-4xl", className)}
      data-testid="entity-convergence-workbench"
      data-kf-a-beat={beat}
      data-kf-a-lens={lens}
      data-selected={selectedId ?? ""}
      data-reduced={reduced ? "1" : "0"}
      data-single-field="1"
    >
      <div className="mb-3 flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
        <div className="min-w-0 flex-1">
          <p className="text-[10px] font-semibold uppercase tracking-wide text-[color:var(--g-text-muted)]">
            Illustrative exact match
          </p>
          <p className="mt-0.5 text-sm font-medium text-[color:var(--g-text-secondary)]" aria-live="polite">
            {BEAT_CAPTION[beat]}
          </p>
        </div>
        <CompactControls
          beat={beat}
          beatIndex={beatIndex}
          total={KF_A_BEATS.length}
          onBack={stepBack}
          onForward={stepForward}
          onReplay={replay}
          onReset={reset}
        />
      </div>

      {/* Single structured field — mentions live here only */}
      <div
        className="relative overflow-hidden rounded-2xl border border-[color:var(--color-line,#eaedf1)] bg-[color:color-mix(in_srgb,#fafbfc_92%,white)]"
        data-testid="kf-a-field"
      >
        <svg
          viewBox="0 0 400 240"
          className="h-auto w-full"
          role="img"
          aria-label="Knowledge field — illustrative entity convergence"
        >
          {/* Column guides — fine technical linework, not wallpaper grid */}
          <line x1="200" y1="28" x2="200" y2="220" stroke="#e4e7ec" strokeWidth="1" strokeDasharray="2 4" />
          <text x="72" y="24" textAnchor="middle" fontSize="9" fontWeight="600" fill="var(--g-text-muted)">
            CRM
          </text>
          <text x="328" y="24" textAnchor="middle" fontSize="9" fontWeight="600" fill="var(--g-text-muted)">
            Email
          </text>

          {/* Match relationship traces */}
          {showMatch && canResolveAcme === false && matchSet.has("m1") && matchSet.has("m2") ? (
            <line
              x1={NODE_LAYOUT.m1!.x}
              y1={NODE_LAYOUT.m1!.y}
              x2={NODE_LAYOUT.m2!.x}
              y2={NODE_LAYOUT.m2!.y}
              stroke={CREATIVE_TOKENS.brand}
              strokeWidth="1.5"
              opacity={0.85}
              data-testid="kf-a-match-trace"
            />
          ) : null}

          {/* Resolve continuity traces (from origin toward anchor while settling) */}
          {canResolveAcme
            ? matchGroupIds.map((id) => {
                const origin = NODE_LAYOUT[id]!
                return (
                  <line
                    key={`rt-${id}`}
                    x1={origin.x}
                    y1={origin.y}
                    x2={RESOLVE_ANCHOR.x}
                    y2={RESOLVE_ANCHOR.y}
                    stroke={CREATIVE_TOKENS.brand}
                    strokeWidth="1.25"
                    opacity={0.35}
                  />
                )
              })
            : null}

          {/* Reject — dashed non-edge emphasizing separation */}
          {showReject ? (
            <g data-testid="kf-a-reject-gap">
              <line
                x1={48}
                y1={168}
                x2={352}
                y2={168}
                stroke="var(--g-intelligence)"
                strokeWidth="1"
                strokeDasharray="4 5"
                opacity="0.45"
              />
              <text
                x="200"
                y="158"
                textAnchor="middle"
                fontSize="9"
                fontWeight="600"
                fill="var(--g-intelligence)"
              >
                no match · sarah ≠ sarah smith
              </text>
            </g>
          ) : null}

          {/* Mention nodes — sole interactive objects */}
          {mentions.map((m) => {
            const pos = nodePosition(m.id)
            const base = NODE_LAYOUT[m.id]!
            const isSelected = selectedId === m.id
            const inMatch = matchSet.has(m.id)
            const isRejected = showReject && rejectIds.has(m.id)
            const isConverged = canResolveAcme && inMatch
            const dimmed =
              selectedId != null &&
              !isSelected &&
              !(inMatch && showMatch) &&
              !(isRejected && showReject)

            const labelY = isConverged ? pos.y + 28 : pos.y + 22
            const shown = isConverged ? "" : displayLabel(m)
            const rawPeek = isSelected && showNorm && beat === "normalize"

            return (
              <g
                key={m.id}
                opacity={dimmed ? 0.28 : 1}
                style={{ cursor: "pointer" }}
                onClick={() => selectObject(isSelected ? null : m.id)}
                data-testid={`kf-a-node-${m.id}`}
                data-selected={isSelected ? "1" : "0"}
                data-matched={inMatch && showMatch ? "1" : "0"}
                data-rejected={isRejected ? "1" : "0"}
              >
                {/* Selection response — soft ring */}
                {isSelected ? (
                  <circle
                    cx={pos.x}
                    cy={pos.y}
                    r={16}
                    fill="none"
                    stroke={CREATIVE_TOKENS.brand}
                    strokeWidth="1"
                    opacity="0.45"
                    className={transition}
                  />
                ) : null}
                {/* Ghost twin edge on select (Acme ↔ email twin before match beat) */}
                {isSelected && m.entityKey === "acme-corp" && !showMatch ? (
                  <line
                    x1={base.x}
                    y1={base.y}
                    x2={m.id === "m1" ? NODE_LAYOUT.m2!.x : NODE_LAYOUT.m1!.x}
                    y2={m.id === "m1" ? NODE_LAYOUT.m2!.y : NODE_LAYOUT.m1!.y}
                    stroke={CREATIVE_TOKENS.brand}
                    strokeWidth="1"
                    strokeDasharray="3 3"
                    opacity="0.4"
                    data-testid="kf-a-select-response"
                  />
                ) : null}
                <circle
                  cx={pos.x}
                  cy={pos.y}
                  r={isSelected || isConverged ? 8 : 6.5}
                  fill={
                    isRejected
                      ? "color-mix(in srgb, var(--g-intelligence) 22%, white)"
                      : isConverged || (inMatch && showMatch)
                        ? CREATIVE_TOKENS.brand
                        : "#fff"
                  }
                  stroke={
                    isRejected
                      ? "var(--g-intelligence)"
                      : isSelected || isConverged || (inMatch && showMatch)
                        ? CREATIVE_TOKENS.brand
                        : "#b8bec8"
                  }
                  strokeWidth="1.5"
                  className={transition}
                />
                {shown ? (
                  <text
                    x={pos.x}
                    y={labelY}
                    textAnchor="middle"
                    fontSize="10"
                    fontWeight={isSelected ? 700 : 600}
                    fill={
                      isRejected
                        ? "var(--g-intelligence)"
                        : isSelected
                          ? CREATIVE_TOKENS.brand
                          : "var(--g-text-secondary)"
                    }
                    className={transition}
                  >
                    {shown}
                  </text>
                ) : null}
                {rawPeek ? (
                  <text
                    x={pos.x}
                    y={labelY + 14}
                    textAnchor="middle"
                    fontSize="8"
                    fill="var(--g-text-muted)"
                    data-testid={`kf-a-norm-${m.id}`}
                  >
                    was “{m.raw}”
                  </text>
                ) : null}
                {showNorm && !rawPeek && !isConverged && isSelected ? (
                  <text
                    x={pos.x}
                    y={labelY + 14}
                    textAnchor="middle"
                    fontSize="8"
                    fontFamily="ui-monospace, monospace"
                    fill="var(--g-text-muted)"
                    data-testid={`kf-a-norm-${m.id}`}
                  >
                    → {m.normalized}
                  </text>
                ) : null}
              </g>
            )
          })}

          {/* Resolved identity — continuous from matched nodes */}
          {canResolveAcme ? (
            <g data-testid="kf-a-resolved">
              <rect
                x="126"
                y="54"
                width="148"
                height={showEvidence ? 52 : 40}
                rx="8"
                fill="#fff"
                stroke={CREATIVE_TOKENS.brand}
                strokeWidth="1.75"
              />
              <text
                x="200"
                y="74"
                textAnchor="middle"
                fontSize="12"
                fontWeight="700"
                fill={CREATIVE_TOKENS.brand}
              >
                Acme Corp
              </text>
              <text x="200" y="88" textAnchor="middle" fontSize="8" fill="var(--g-text-muted)">
                resolved identity
              </text>
              {showEvidence ? (
                <g transform="translate(148 94)" data-testid="kf-a-evidence">
                  <rect
                    width="104"
                    height="16"
                    rx="3"
                    fill="var(--g-intelligence-soft)"
                    stroke="color-mix(in oklch, var(--g-intelligence) 35%, #eaedf1)"
                  />
                  <circle cx="8" cy="8" r="2.5" fill="var(--g-intelligence)" />
                  <text x="16" y="11" fontSize="8" fontWeight="600" fill="var(--g-intelligence)">
                    CRM · Email evidence
                  </text>
                </g>
              ) : null}
            </g>
          ) : null}

          {showMatch && matchSet.size >= 2 && !canResolveAcme ? (
            <text
              x="200"
              y="118"
              textAnchor="middle"
              fontSize="10"
              fontWeight="600"
              fill={CREATIVE_TOKENS.brand}
              data-testid="kf-a-match-decision"
            >
              Exact match: “acme corp” = “acme corp”
            </text>
          ) : null}

          {showReject ? (
            <text
              x="200"
              y="210"
              textAnchor="middle"
              fontSize="10"
              fontWeight="600"
              fill="var(--g-intelligence)"
              data-testid="kf-a-reject-decision"
            >
              Kept separate — no fuzzy person matching
            </text>
          ) : null}
        </svg>

        {/* Inline inspect — contextual under field, not permanent sidebar */}
        {selected ? (
          <div
            className="border-t border-[color:var(--color-line,#eaedf1)] bg-white/90 px-4 py-2.5"
            data-testid="kf-a-inspect"
          >
            <p className="text-[10px] font-semibold uppercase tracking-wide text-[color:var(--g-text-muted)]">
              Inspect · {selected.source.toUpperCase()}
            </p>
            <p className="mt-1 text-[12px] text-[color:var(--g-text-secondary)]">
              <span className="font-semibold">“{selected.raw}”</span>
              {showNorm ? (
                <>
                  {" "}
                  → <span className="font-mono text-[11px]">“{normalizeIllustrativeMention(selected.raw)}”</span>
                </>
              ) : null}
            </p>
            {selected.fuzzyPersonDemo ? (
              <p className="mt-1 text-[11px] text-[color:var(--g-intelligence)]">
                No entity key — never merges with other person mentions.
              </p>
            ) : selected.entityKey ? (
              <p className="mt-1 text-[11px] text-[color:var(--g-text-muted)]">
                Illustrative entity key: {selected.entityKey}
              </p>
            ) : null}
            {showEvidence && canResolveAcme && selected.entityKey === "acme-corp" ? (
              <div className="mt-2">
                <GravitreEvidenceMark label="Exact normalized match" />
              </div>
            ) : null}
          </div>
        ) : null}
      </div>

      {compareMode ? (
        <div className="mt-2 flex items-center justify-center gap-2" data-testid="kf-a-compare-lens">
          <button
            type="button"
            className={cn(
              "rounded-md border px-2.5 py-1 text-[11px] font-semibold",
              !compareResolved
                ? "border-[color:var(--color-brand,#16a374)] text-[color:var(--color-brand,#16a374)]"
                : "border-[color:var(--color-line,#eaedf1)] text-[color:var(--g-text-muted)]",
            )}
            onClick={() => setCompareResolved(false)}
            aria-pressed={!compareResolved}
          >
            Fragmented
          </button>
          <button
            type="button"
            className={cn(
              "rounded-md border px-2.5 py-1 text-[11px] font-semibold",
              compareResolved
                ? "border-[color:var(--color-brand,#16a374)] text-[color:var(--color-brand,#16a374)]"
                : "border-[color:var(--color-line,#eaedf1)] text-[color:var(--g-text-muted)]",
            )}
            onClick={() => setCompareResolved(true)}
            aria-pressed={compareResolved}
          >
            Resolved
          </button>
        </div>
      ) : null}

      <p className="mt-3 text-[11px] text-[color:var(--g-text-muted)]">
        Illustrative · shared normalize function · not live CRM sync · not fuzzy person ER · not customer telemetry.
      </p>
    </div>
  )
}

export const EntityConvergenceWorkbenchField = withCreativeScene(
  EntityConvergenceWorkbench,
  "knowledge-fabric-workbench",
)
