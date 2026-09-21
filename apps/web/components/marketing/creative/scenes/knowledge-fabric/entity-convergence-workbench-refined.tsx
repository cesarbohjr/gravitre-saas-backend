"use client"

/**
 * CES 2.0 KF-A — refined Entity Convergence Workbench (harness / preview only).
 *
 * Direction: quiet chrome around a living knowledge structure.
 * Narrative: arrive → normalize → match → resolve (converge + reject together)
 * → evidence attaches → structured knowledge persists.
 *
 * Production /features/technology continues to mount the stable workbench until
 * Cesar confirms public promotion of this refined edition.
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

/** Semantic pipeline — not playback chrome. */
export const KF_A_REFINED_BEATS = [
  "arrive",
  "normalize",
  "match",
  "resolve",
  "evidence",
  "knowledge",
] as const

export type KfARefinedBeat = (typeof KF_A_REFINED_BEATS)[number]

const PIPELINE: { id: KfARefinedBeat; label: string }[] = [
  { id: "arrive", label: "Arrive" },
  { id: "normalize", label: "Normalize" },
  { id: "match", label: "Match" },
  { id: "resolve", label: "Resolve" },
  { id: "evidence", label: "Evidence" },
  { id: "knowledge", label: "Knowledge" },
]

const BEAT_CAPTION: Record<KfARefinedBeat, string> = {
  arrive: "Information arrives as separate mentions from CRM and email.",
  normalize: "Each mention is normalized — same rules, no guessing.",
  match: "Exact normalized strings match. Different strings stay apart.",
  resolve: "Matching mentions converge into one identity. Rejected pairs stay visibly separate.",
  evidence: "Source evidence attaches to the resolved identity — part of the structure.",
  knowledge: "Structured knowledge remains in the field — not a reset, not a decorative end card.",
}

type MentionView = ReturnType<typeof mentionWithNormalized>

const NODE_LAYOUT: Record<string, { x: number; y: number }> = {
  m1: { x: 78, y: 72 },
  m2: { x: 322, y: 72 },
  m3: { x: 78, y: 168 },
  m4: { x: 322, y: 168 },
}

const RESOLVE_ANCHOR = { x: 200, y: 72 }
const REJECT_LEFT = { x: 56, y: 176 }
const REJECT_RIGHT = { x: 344, y: 176 }

function CompactControls({
  beatIndex,
  total,
  onBack,
  onForward,
  onReplay,
  onReset,
}: {
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
      data-testid="kf-a-refined-controls"
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

function PipelineRail({ active }: { active: KfARefinedBeat }) {
  const activeIdx = PIPELINE.findIndex((p) => p.id === active)
  return (
    <ol
      className="mb-3 flex flex-wrap items-center gap-x-1 gap-y-1.5"
      aria-label="Knowledge formation pipeline"
      data-testid="kf-a-refined-pipeline"
    >
      {PIPELINE.map((step, i) => {
        const done = i < activeIdx
        const current = i === activeIdx
        return (
          <li key={step.id} className="flex items-center gap-1">
            {i > 0 ? (
              <span
                className={cn(
                  "mx-0.5 hidden h-px w-3 sm:block",
                  done || current ? "bg-[color:var(--color-brand,#16a374)]" : "bg-[color:var(--color-line,#eaedf1)]",
                )}
                aria-hidden
              />
            ) : null}
            <span
              className={cn(
                "rounded-full px-2 py-0.5 text-[10px] font-semibold tracking-wide",
                current
                  ? "bg-[color:var(--color-brand,#16a374)] text-white"
                  : done
                    ? "bg-[color:color-mix(in_srgb,var(--color-brand,#16a374)_12%,white)] text-[color:var(--color-brand,#16a374)]"
                    : "bg-[color:var(--g-canvas,#f6f7f9)] text-[color:var(--g-text-muted)]",
              )}
              data-pipeline-step={step.id}
              data-active={current ? "1" : "0"}
              data-done={done ? "1" : "0"}
            >
              {step.label}
            </span>
          </li>
        )
      })}
    </ol>
  )
}

export function EntityConvergenceWorkbenchRefined({ className }: { className?: string }) {
  const reducedPref = useReducedMotion()
  const reduced = !!reducedPref
  const mentions = useMemo(() => KF_A_MENTIONS.map(mentionWithNormalized), [])

  const ctrl = useSceneController(KF_A_REFINED_BEATS, { mode: "stepped" })
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
  /** On knowledge beat, visitor may peek fragmented — structure otherwise persists resolved. */
  const [showFragmented, setShowFragmented] = useState(false)
  useEffect(() => {
    if (beat !== "knowledge") setShowFragmented(false)
  }, [beat])

  const showNorm = beat !== "arrive"
  const showMatch = ["match", "resolve", "evidence", "knowledge"].includes(beat)
  const showResolve =
    ["resolve", "evidence", "knowledge"].includes(beat) && !(beat === "knowledge" && showFragmented)
  const showEvidence = ["evidence", "knowledge"].includes(beat) && showResolve
  /** Rejected pair visible from match onward — concurrent with converge, not a later detour. */
  const showReject = ["match", "resolve", "evidence", "knowledge"].includes(beat)
  const knowledgePersist = beat === "knowledge" && !showFragmented

  const matchGroupIds = useMemo(() => {
    if (!showMatch) return [] as string[]
    return mentions.filter((m) => m.entityKey === "acme-corp").map((m) => m.id)
  }, [mentions, showMatch])

  const matchSet = new Set(matchGroupIds)
  const canResolveAcme = matchGroupIds.length >= 2 && showResolve
  const rejectIds = new Set(["m3", "m4"])

  function nodePosition(id: string): { x: number; y: number } {
    const base = NODE_LAYOUT[id]!
    if (canResolveAcme && matchSet.has(id) && !reduced) return RESOLVE_ANCHOR
    if (showReject && rejectIds.has(id) && !reduced) {
      return id === "m3" ? REJECT_LEFT : REJECT_RIGHT
    }
    return { x: base.x, y: base.y }
  }

  function displayLabel(m: MentionView): string {
    if (!showNorm) return m.raw
    return m.normalized
  }

  const transition = reduced ? undefined : "transition-[cx,cy,opacity,r] duration-700 ease-[cubic-bezier(0.22,1,0.36,1)]"

  return (
    <div
      className={cn("mx-auto w-full max-w-4xl", className)}
      data-testid="entity-convergence-workbench-refined"
      data-kf-a-edition="refined"
      data-kf-a-beat={beat}
      data-selected={selectedId ?? ""}
      data-reduced={reduced ? "1" : "0"}
      data-knowledge-persist={knowledgePersist ? "1" : "0"}
    >
      <PipelineRail active={beat} />

      <div className="mb-3 flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
        <div className="min-w-0 flex-1">
          <p className="text-[10px] font-semibold uppercase tracking-wide text-[color:var(--g-text-muted)]">
            Illustrative exact match · refined preview
          </p>
          <p className="mt-0.5 text-sm font-medium text-[color:var(--g-text-secondary)]" aria-live="polite">
            {BEAT_CAPTION[beat]}
          </p>
        </div>
        <CompactControls
          beatIndex={beatIndex}
          total={KF_A_REFINED_BEATS.length}
          onBack={stepBack}
          onForward={stepForward}
          onReplay={replay}
          onReset={reset}
        />
      </div>

      <div
        className="relative overflow-hidden rounded-2xl border border-[color:var(--color-line,#eaedf1)] bg-white"
        data-testid="kf-a-refined-field"
      >
        {/* Quiet source washes — atmosphere without grid wallpaper */}
        <div
          className="pointer-events-none absolute inset-y-0 left-0 w-1/2 bg-[color:color-mix(in_srgb,#f4f6f8_70%,white)]"
          aria-hidden
        />
        <div
          className="pointer-events-none absolute inset-y-0 right-0 w-1/2 bg-[color:color-mix(in_srgb,#fafbfc_85%,white)]"
          aria-hidden
        />

        <svg
          viewBox="0 0 400 260"
          className="relative h-auto w-full"
          role="img"
          aria-label="Knowledge field — information arriving through structured resolution"
        >
          <text x="78" y="22" textAnchor="middle" fontSize="9" fontWeight="600" fill="var(--g-text-muted)">
            CRM
          </text>
          <text x="322" y="22" textAnchor="middle" fontSize="9" fontWeight="600" fill="var(--g-text-muted)">
            Email
          </text>

          {/* Match relationship — before converge */}
          {showMatch && !canResolveAcme && matchSet.has("m1") && matchSet.has("m2") ? (
            <line
              x1={NODE_LAYOUT.m1!.x}
              y1={NODE_LAYOUT.m1!.y}
              x2={NODE_LAYOUT.m2!.x}
              y2={NODE_LAYOUT.m2!.y}
              stroke={CREATIVE_TOKENS.brand}
              strokeWidth="1.5"
              opacity={0.8}
              data-testid="kf-a-refined-match-trace"
            />
          ) : null}

          {/* Continuity traces into resolve */}
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
                    strokeWidth="1.2"
                    opacity={0.28}
                  />
                )
              })
            : null}

          {/* Reject gap — concurrent with match/resolve/knowledge */}
          {showReject ? (
            <g data-testid="kf-a-refined-reject-gap">
              <line
                x1={REJECT_LEFT.x}
                y1={REJECT_LEFT.y}
                x2={REJECT_RIGHT.x}
                y2={REJECT_RIGHT.y}
                stroke="var(--g-intelligence)"
                strokeWidth="1"
                strokeDasharray="3 5"
                opacity="0.4"
              />
              <text
                x="200"
                y="156"
                textAnchor="middle"
                fontSize="9"
                fontWeight="600"
                fill="var(--g-intelligence)"
              >
                no match · sarah ≠ sarah smith
              </text>
            </g>
          ) : null}

          {mentions.map((m) => {
            const pos = nodePosition(m.id)
            const isSelected = selectedId === m.id
            const inMatch = matchSet.has(m.id)
            const isRejected = showReject && rejectIds.has(m.id)
            const isConverged = canResolveAcme && inMatch
            const dimmed =
              selectedId != null && !isSelected && !(inMatch && showMatch) && !(isRejected && showReject)
            const labelY = isConverged ? pos.y + 30 : pos.y + 22
            const shown = isConverged ? "" : displayLabel(m)
            const rawPeek = isSelected && beat === "normalize"

            return (
              <g
                key={m.id}
                opacity={dimmed ? 0.22 : 1}
                style={{ cursor: "pointer" }}
                onClick={() => selectObject(isSelected ? null : m.id)}
                data-testid={`kf-a-refined-node-${m.id}`}
                data-selected={isSelected ? "1" : "0"}
                data-matched={inMatch && showMatch ? "1" : "0"}
                data-rejected={isRejected ? "1" : "0"}
              >
                {isSelected ? (
                  <circle
                    cx={pos.x}
                    cy={pos.y}
                    r={17}
                    fill="none"
                    stroke={CREATIVE_TOKENS.brand}
                    strokeWidth="1"
                    opacity="0.4"
                    className={transition}
                  />
                ) : null}
                <circle
                  cx={pos.x}
                  cy={pos.y}
                  r={isSelected || isConverged ? 8 : 6.5}
                  fill={
                    isRejected
                      ? "color-mix(in srgb, var(--g-intelligence) 18%, white)"
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
                    data-testid={`kf-a-refined-norm-${m.id}`}
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
                  >
                    → {m.normalized}
                  </text>
                ) : null}
              </g>
            )
          })}

          {/* Resolved identity — evidence grows into the structure */}
          {canResolveAcme ? (
            <g data-testid="kf-a-refined-resolved">
              <rect
                x="118"
                y={showEvidence ? 44 : 52}
                width="164"
                height={showEvidence ? 64 : 40}
                rx="10"
                fill="#fff"
                stroke={CREATIVE_TOKENS.brand}
                strokeWidth="1.75"
              />
              <text
                x="200"
                y={showEvidence ? 64 : 70}
                textAnchor="middle"
                fontSize="12"
                fontWeight="700"
                fill={CREATIVE_TOKENS.brand}
              >
                Acme Corp
              </text>
              <text
                x="200"
                y={showEvidence ? 78 : 84}
                textAnchor="middle"
                fontSize="8"
                fill="var(--g-text-muted)"
              >
                {knowledgePersist ? "structured knowledge" : "resolved identity"}
              </text>
              {showEvidence ? (
                <g transform="translate(140 88)" data-testid="kf-a-refined-evidence">
                  <rect
                    width="120"
                    height="16"
                    rx="4"
                    fill="var(--g-intelligence-soft)"
                    stroke="color-mix(in oklch, var(--g-intelligence) 30%, #eaedf1)"
                  />
                  <circle cx="9" cy="8" r="2.5" fill="var(--g-intelligence)" />
                  <text x="17" y="11" fontSize="8" fontWeight="600" fill="var(--g-intelligence)">
                    CRM · Email · exact match
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
              data-testid="kf-a-refined-match-decision"
            >
              Exact match: “acme corp” = “acme corp”
            </text>
          ) : null}
        </svg>

        {selected ? (
          <div
            className="relative border-t border-[color:var(--color-line,#eaedf1)] bg-white/95 px-4 py-2.5"
            data-testid="kf-a-refined-inspect"
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

      {beat === "knowledge" ? (
        <div className="mt-2 flex items-center justify-center gap-2" data-testid="kf-a-refined-knowledge-lens">
          <button
            type="button"
            className={cn(
              "rounded-md border px-2.5 py-1 text-[11px] font-semibold",
              showFragmented
                ? "border-[color:var(--color-brand,#16a374)] text-[color:var(--color-brand,#16a374)]"
                : "border-[color:var(--color-line,#eaedf1)] text-[color:var(--g-text-muted)]",
            )}
            onClick={() => setShowFragmented(true)}
            aria-pressed={showFragmented}
          >
            Fragmented peek
          </button>
          <button
            type="button"
            className={cn(
              "rounded-md border px-2.5 py-1 text-[11px] font-semibold",
              !showFragmented
                ? "border-[color:var(--color-brand,#16a374)] text-[color:var(--color-brand,#16a374)]"
                : "border-[color:var(--color-line,#eaedf1)] text-[color:var(--g-text-muted)]",
            )}
            onClick={() => setShowFragmented(false)}
            aria-pressed={!showFragmented}
          >
            Knowledge remains
          </button>
        </div>
      ) : null}

      <p className="mt-3 text-[11px] text-[color:var(--g-text-muted)]">
        Harness preview · illustrative normalize · not live CRM sync · not fuzzy person ER · not customer telemetry ·
        not promoted to /features/technology until confirmed.
      </p>
    </div>
  )
}

export const EntityConvergenceWorkbenchRefinedField = withCreativeScene(
  EntityConvergenceWorkbenchRefined,
  "knowledge-fabric-workbench-refined",
)
