"use client"

/**
 * ProductStage — UI 3.0 Hybrid A+B product composition shell.
 *
 * A (layered): operational panels composed as a stage.
 * B (living): single surface with Intent → Tool → Approval → Verified beats.
 *
 * Does not replace ProductFrame (screenshot chrome). Phase 3 marketing
 * will compose real captures / live UI inside this stage.
 */

import { cn } from "@/lib/utils"
import { RADIUS } from "@/lib/design-system"
import { PulseDot } from "./pulse-dot"
import { ResolveMark } from "./resolve-mark"
import { TracePath, TRACE_PATH_HYBRID_BEAT } from "./trace-path"
import { StatusChip } from "./status-chip"

export type ProductStageBeat =
  | "idle"
  | "intent"
  | "tool"
  | "approval"
  | "verified"

export type ProductStageProps = {
  children?: React.ReactNode
  className?: string
  chromeLabel?: string
  /** Hybrid A layered stack vs B living single surface. */
  composition?: "layered" | "living"
  /** Current B choreography beat (also drives status strip). */
  beat?: ProductStageBeat
  /** Show Trace + status strip for living composition. */
  showTrace?: boolean
  /** Optional caption under the stage. */
  caption?: string
}

const BEAT_LABEL: Record<ProductStageBeat, string> = {
  idle: "Ready",
  intent: "Intent received",
  tool: "Tool running",
  approval: "Approval needed",
  verified: "Verified",
}

function beatTone(beat: ProductStageBeat) {
  switch (beat) {
    case "intent":
      return "running" as const
    case "tool":
      return "running" as const
    case "approval":
      return "pending" as const
    case "verified":
      return "verified" as const
    default:
      return "idle" as const
  }
}

function beatProgress(beat: ProductStageBeat): number {
  switch (beat) {
    case "idle":
      return 0
    case "intent":
      return 0.25
    case "tool":
      return 0.5
    case "approval":
      return 0.75
    case "verified":
      return 1
  }
}

export function ProductStage({
  children,
  className,
  chromeLabel = "gravitre",
  composition = "layered",
  beat = "idle",
  showTrace = composition === "living",
  caption,
}: ProductStageProps) {
  const living = composition === "living"

  return (
    <figure className={cn("relative w-full", className)}>
      {living ? (
        <div
          className="pointer-events-none absolute -inset-6 -z-10 rounded-[2rem] opacity-70"
          style={{ background: "var(--g-light-neutral)" }}
          aria-hidden
        />
      ) : null}

      <div
        className={cn(
          "g-material-panel relative overflow-hidden border border-[color:var(--g-border-default)] bg-[color:var(--g-surface-1)]",
          RADIUS.panel,
        )}
        style={{
          boxShadow: "var(--g-highlight-top), var(--g-shadow-product)",
        }}
        data-product-stage={composition}
        data-product-beat={beat}
      >
        <div className="flex items-center justify-between gap-3 border-b border-[color:var(--g-border-subtle)] bg-[color:var(--g-surface-2)] px-4 py-2.5">
          <div className="flex items-center gap-2">
            <div className="flex gap-1.5" aria-hidden>
              <span className="h-2.5 w-2.5 rounded-full bg-muted-foreground/30" />
              <span className="h-2.5 w-2.5 rounded-full bg-muted-foreground/22" />
              <span className="h-2.5 w-2.5 rounded-full bg-[color:var(--g-emerald)]/55" />
            </div>
            <span className="text-[11px] font-medium tracking-wide text-[color:var(--g-text-muted)]">
              {chromeLabel}
            </span>
          </div>
          <div className="flex items-center gap-2">
            {beat === "tool" || beat === "intent" ? (
              <PulseDot tone={beat === "tool" ? "signal" : "intelligence"} size="sm" label={BEAT_LABEL[beat]} />
            ) : null}
            {beat === "verified" ? <ResolveMark size="sm" /> : null}
            <StatusChip tone={beatTone(beat)} dot={!living} pulse={beat === "tool" || beat === "intent"}>
              {BEAT_LABEL[beat]}
            </StatusChip>
          </div>
        </div>

        {showTrace ? (
          <div className="border-b border-[color:var(--g-border-subtle)] bg-[color:var(--g-surface-1)] px-3 py-2">
            <TracePath
              d={TRACE_PATH_HYBRID_BEAT}
              progress={beatProgress(beat)}
              tone={
                beat === "approval"
                  ? "approval"
                  : beat === "verified"
                    ? "emerald"
                    : beat === "tool"
                      ? "signal"
                      : "intelligence"
              }
              label={`Workflow beat: ${BEAT_LABEL[beat]}`}
              className="h-10"
            />
          </div>
        ) : null}

        <div
          className={cn(
            "relative bg-[color:var(--g-surface-1)]",
            living ? "min-h-[220px] p-4 sm:p-5" : "min-h-[200px] p-3 sm:p-4",
            composition === "layered" && "space-y-3",
          )}
        >
          {children ?? (
            <p className="text-sm text-[color:var(--g-text-muted)]">
              Product stage — compose real Gravitre surfaces here (Phase 3).
            </p>
          )}
        </div>
      </div>

      {caption ? (
        <figcaption className="mt-3 text-center text-xs text-[color:var(--g-text-muted)]">
          {caption}
        </figcaption>
      ) : null}
    </figure>
  )
}
