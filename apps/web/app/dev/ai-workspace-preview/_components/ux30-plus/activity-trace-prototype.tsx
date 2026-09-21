"use client"

import { useMemo, useState } from "react"
import { AnimatePresence, motion } from "framer-motion"
import { Button } from "@/components/ui/button"
import { EvidenceChip, grammarToneForStepStatus } from "@/components/gravitre/creative-grammar"
import { NucleoActivity } from "@/components/icons/nucleo/semantic"
import { TYPE } from "@/lib/design-system"
import { cn } from "@/lib/utils"
import { useMotionPrefs } from "@/lib/animations"
import {
  HARNESS_FIXTURE_LABEL,
  HARNESS_OUTCOMES,
  TRACE_STAGE_ORDER,
  type HarnessOutcome,
  type HarnessTraceStage,
} from "./fixtures"
import { HarnessSurface, TopologyEdge } from "./topology-primitives"
import { BeforeAfterPanel } from "./before-after-panel"

const STAGE_STATUS_COLOR: Record<string, string> = {
  verified: "var(--g-emerald)",
  running: "var(--g-signal)",
  waiting: "var(--g-approval)",
  failed: "var(--g-danger)",
  pending: "var(--g-border-default)",
}

function stageTone(status: HarnessTraceStage["status"]) {
  return grammarToneForStepStatus(
    status === "verified" ? "verified" : status === "failed" ? "failed" : status === "waiting" ? "awaiting_approval" : status,
  )
}

export function ActivityTracePrototype({ scene }: { scene: string }) {
  const { reduced } = useMotionPrefs()
  const forceReduced = scene.includes("reduced") || reduced
  const isMobile = scene.includes("mobile")
  const isLoading = scene.includes("loading")
  const isEmpty = scene.includes("empty")
  const isError = scene.includes("error")
  const showInspector = scene.includes("inspector") || scene.includes("selected") || scene.includes("ai")
  const showAi = scene.includes("ai")

  const defaultOutcome = scene.includes("fail") ? HARNESS_OUTCOMES[1] : HARNESS_OUTCOMES[0]
  const [viewMode, setViewMode] = useState<"story" | "timeline">(
    scene.includes("timeline") ? "timeline" : "story",
  )
  const isTimeline = viewMode === "timeline"
  const [selectedId, setSelectedId] = useState(defaultOutcome.id)
  const [activeStageId, setActiveStageId] = useState<string | null>(() => {
    if (scene.includes("fail")) return "tool"
    if (showInspector) return defaultOutcome.status === "failed" ? "tool" : "verification"
    return null
  })

  const outcome = HARNESS_OUTCOMES.find((o) => o.id === selectedId) ?? defaultOutcome
  const activeStage = outcome.stages.find((s) => s.id === activeStageId)

  const totalMs = useMemo(
    () => outcome.stages.reduce((sum, s) => sum + (s.durationMs ?? 0), 0),
    [outcome.stages],
  )

  return (
    <div data-review-surface="activity" data-review-scene={scene}>
      <div className={cn("flex flex-col", isMobile ? "max-w-[390px]" : "min-h-[640px]")}>
        <div className="flex items-center justify-between gap-3 border-b border-[color:var(--g-border-subtle)] pb-3">
          <div className="flex items-center gap-2">
            <NucleoActivity size={20} />
            <h2 className={TYPE.pageTitle}>Activity</h2>
          </div>
          <div className="flex gap-2">
            <Button
              type="button"
              size="sm"
              variant={!isTimeline ? "secondary" : "outline"}
              disabled={isEmpty || isLoading}
              onClick={() => setViewMode("story")}
            >
              Story
            </Button>
            <Button
              type="button"
              size="sm"
              variant={isTimeline ? "secondary" : "outline"}
              disabled={isEmpty || isLoading}
              onClick={() => setViewMode("timeline")}
            >
              Timeline
            </Button>
          </div>
        </div>
        <p className={cn(TYPE.meta, "mt-1")}>{HARNESS_FIXTURE_LABEL}</p>

        {isError ? (
          <div className="mt-6 rounded-xl border border-[color:var(--g-danger)]/30 bg-[color:var(--g-danger)]/5 p-6 text-center">
            <p className="text-sm font-medium text-[color:var(--g-danger)]">Could not load activity</p>
            <Button type="button" size="sm" variant="outline" className="mt-3">
              Retry
            </Button>
          </div>
        ) : null}

        {!isError ? (
          <div className={cn("mt-4 flex flex-1 gap-3", isMobile ? "flex-col" : "flex-row")}>
            {/* Queue list */}
            {!isMobile || !showInspector ? (
              <HarnessSurface className={cn("shrink-0 overflow-hidden", isMobile ? "w-full" : "w-[280px]")}>
                {isLoading ? (
                  <div className="space-y-2 p-3">
                    {[1, 2, 3].map((i) => (
                      <div key={i} className="h-14 animate-pulse rounded-lg bg-[color:var(--g-surface-2)]" />
                    ))}
                  </div>
                ) : isEmpty ? (
                  <p className={cn(TYPE.bodyMuted, "p-6 text-center")}>No activity yet</p>
                ) : (
                  <ul role="listbox" className="max-h-[520px] overflow-y-auto">
                    {HARNESS_OUTCOMES.map((o) => (
                      <li key={o.id}>
                        <button
                          type="button"
                          role="option"
                          aria-selected={selectedId === o.id}
                          onClick={() => {
                            setSelectedId(o.id)
                            setActiveStageId(null)
                          }}
                          className={cn(
                            "relative w-full border-b border-[color:var(--g-border-subtle)] px-3 py-3 text-left",
                            selectedId === o.id && "bg-[color:var(--g-surface-active)]",
                          )}
                        >
                          {selectedId === o.id ? (
                            <motion.span
                              layoutId={forceReduced ? undefined : "activity-accent"}
                              className="absolute inset-y-0 left-0 w-0.5 bg-[color:var(--g-emerald)]"
                            />
                          ) : null}
                          <p className="text-sm font-medium text-[color:var(--g-text-primary)]">{o.title}</p>
                          <p className={cn(TYPE.meta, "mt-0.5")}>
                            {o.createdAt} · {o.status}
                          </p>
                        </button>
                      </li>
                    ))}
                  </ul>
                )}
              </HarnessSurface>
            ) : null}

            {/* A1 TRACE rail + story OR A2 timeline */}
            {!isEmpty && !isLoading ? (
              <div className="flex min-w-0 flex-1 gap-3">
                {!isTimeline ? (
                  <>
                    {/* Vertical TRACE rail */}
                    <HarnessSurface className="hidden w-[52px] shrink-0 py-4 md:block">
                      <div className="flex h-full flex-col items-center justify-between">
                        {TRACE_STAGE_ORDER.map((stageId, i) => {
                          const stage = outcome.stages.find((s) => s.id === stageId)
                          if (!stage) return null
                          const isActive = activeStageId === stage.id
                          const isFailed = stage.status === "failed"
                          return (
                            <button
                              key={stage.id}
                              type="button"
                              title={stage.label}
                              onClick={() => setActiveStageId(stage.id)}
                              className="group flex flex-col items-center gap-1"
                            >
                              <span
                                className={cn(
                                  "flex h-6 w-6 items-center justify-center rounded-full border text-[9px] font-semibold",
                                  isActive && "ring-2 ring-[color:var(--g-emerald)] ring-offset-1",
                                )}
                                style={{
                                  borderColor: STAGE_STATUS_COLOR[stage.status],
                                  color: STAGE_STATUS_COLOR[stage.status],
                                }}
                              >
                                {i + 1}
                              </span>
                              {i < TRACE_STAGE_ORDER.length - 1 ? (
                                <span
                                  className="h-6 w-px"
                                  style={{
                                    background:
                                      isFailed && stage.status === "failed"
                                        ? "var(--g-danger)"
                                        : stage.status === "verified"
                                          ? "var(--g-emerald)"
                                          : "var(--g-border-subtle)",
                                  }}
                                />
                              ) : null}
                            </button>
                          )
                        })}
                      </div>
                    </HarnessSurface>

                    {/* Story panel */}
                    <HarnessSurface className="min-w-0 flex-1 p-4">
                      <p className={TYPE.eyebrow}>Execution story</p>
                      <p className={cn(TYPE.cardTitle, "mt-2")}>{outcome.title}</p>
                      <p className={cn(TYPE.meta, "mt-1")}>
                        {outcome.runId} · {outcome.createdAt}
                      </p>
                      <div className="mt-4 space-y-3">
                        {outcome.stages.map((stage) => (
                          <button
                            key={stage.id}
                            type="button"
                            onClick={() => setActiveStageId(stage.id)}
                            className={cn(
                              "w-full rounded-lg border border-[color:var(--g-border-subtle)] px-3 py-2.5 text-left transition-colors",
                              activeStageId === stage.id && "border-[color:var(--g-emerald)] bg-[color:var(--g-surface-active)]",
                            )}
                          >
                            <div className="flex items-center justify-between gap-2">
                              <span className="text-sm font-medium">{stage.label}</span>
                              <EvidenceChip
                                label={stage.status}
                                tone={
                                  stageTone(stage.status) === "failed"
                                    ? "error"
                                    : stageTone(stage.status) === "waiting"
                                      ? "waiting"
                                      : "evidence"
                                }
                              />
                            </div>
                            <p className={cn(TYPE.bodyMuted, "mt-1 text-sm")}>{stage.summary}</p>
                            {stage.durationMs ? (
                              <p className={cn(TYPE.meta, "mt-1 tabular-nums")}>{stage.durationMs}ms</p>
                            ) : null}
                            {stage.evidence?.map((ev) => (
                              <EvidenceChip key={ev} label={ev} tone="evidence" />
                            ))}
                          </button>
                        ))}
                      </div>
                      {showAi ? (
                        <div className="mt-4 rounded-lg border border-[color:var(--g-border-subtle)] bg-[color:var(--g-canvas)] p-3">
                          <p className={TYPE.eyebrow}>Contextual AI</p>
                          <Button type="button" size="sm" variant="outline" className="mt-2">
                            {outcome.status === "failed" ? "Why did this fail?" : "Summarize outcome"}
                          </Button>
                        </div>
                      ) : null}
                    </HarnessSurface>
                  </>
                ) : (
                  /* A2 — Stream timeline (optional temporal view) */
                  <HarnessSurface className="min-w-0 flex-1 p-4">
                    <p className={TYPE.eyebrow}>Temporal analysis · real durations</p>
                    <p className={cn(TYPE.meta, "mt-1 tabular-nums")}>Total {totalMs}ms</p>
                    <svg viewBox="0 0 720 120" className="mt-4 h-auto w-full">
                      {outcome.stages.map((stage, i) => {
                        if (!stage.durationMs) return null
                        const offset = outcome.stages
                          .slice(0, i)
                          .reduce((s, st) => s + (st.durationMs ?? 0), 0)
                        const x = 40 + (offset / totalMs) * 640
                        const w = Math.max(8, (stage.durationMs / totalMs) * 640)
                        const y = 40
                        return (
                          <g key={stage.id}>
                            <TopologyEdge
                              x1={x}
                              y1={y + 20}
                              x2={x + w}
                              y2={y + 20}
                              active={stage.status === "running"}
                              learned={stage.status === "verified"}
                              progress={1}
                              reducedMotion={forceReduced}
                            />
                            <rect
                              x={x}
                              y={y}
                              width={w}
                              height={24}
                              rx={4}
                              fill={
                                stage.status === "failed"
                                  ? "color-mix(in oklch, var(--g-danger) 15%, white)"
                                  : stage.status === "verified"
                                    ? "color-mix(in oklch, var(--g-emerald) 12%, white)"
                                    : "var(--g-surface-2)"
                              }
                              stroke={STAGE_STATUS_COLOR[stage.status]}
                              strokeWidth={1.25}
                            />
                            <text x={x + 4} y={y + 15} className="fill-[color:var(--g-text-primary)] text-[8px]">
                              {stage.label}
                            </text>
                            <text
                              x={x + w - 4}
                              y={y + 36}
                              textAnchor="end"
                              className="fill-[color:var(--g-text-muted)] text-[8px] tabular-nums"
                            >
                              {stage.durationMs}ms
                            </text>
                          </g>
                        )
                      })}
                    </svg>
                    <p className={cn(TYPE.bodyMuted, "mt-3 text-sm")}>
                      Use when timing, parallel execution, or bottleneck analysis matters. Default remains story + rail.
                    </p>
                  </HarnessSurface>
                )}
              </div>
            ) : null}
          </div>
        ) : null}

        {isMobile && showInspector && !isEmpty ? (
          <Button type="button" size="sm" variant="ghost" className="mt-2 self-start">
            ← Back to list
          </Button>
        ) : null}
      </div>

      <BeforeAfterPanel
        surface="activity"
        changes={[
          { action: "removed", detail: "Ambiguous “View in Gravitre” without stage context" },
          { action: "removed", detail: "Generic page description under header" },
          { action: "consolidated", detail: "Outcome detail + trace stages into one story panel" },
          { action: "contextual", detail: "A2 timeline only when temporal analysis is relevant" },
          { action: "visual", detail: "TRACE rail with failure scoped to failed stage only" },
          { action: "clearer", detail: "Evidence chips at verification; durations from fixture timeline" },
        ]}
      />
    </div>
  )
}
