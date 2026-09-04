"use client"

/**
 * GIBE Module C honesty strip — runtime_status over catalog TRAINED.
 * Used on the intelligence landing (Pilot D). Decorative WebGL lives on the page shell, not this strip.
 */

import Link from "next/link"
import { Brain } from "@phosphor-icons/react"
import { Button } from "@/components/ui/button"
import { StatusBadge, formatStatusLabel } from "@/components/gravitre/status-badge"
import { APP_ROUTES } from "@/lib/app-routes"
import { TYPE, RADIUS } from "@/lib/design-system"
import { CONFIDENCE_ESTIMATE_METHODOLOGY } from "@/lib/outcome-labels"
import {
  summarizeOrgTraining,
  type RuntimeHonestyKind,
} from "@/lib/intelligence/model-runtime-honesty"
import type { MlAdminOrgModelStatus } from "@/lib/api"
import { cn } from "@/lib/utils"

const COUNT_LABEL: Record<RuntimeHonestyKind, string> = {
  model_loaded: "artifact-loaded",
  heuristic: "heuristic",
  data_gate: "insufficient data",
  unknown: "unknown / catalog-only",
}

function toneFor(kind: RuntimeHonestyKind) {
  switch (kind) {
    case "model_loaded":
      return "verified" as const
    case "heuristic":
      return "estimate" as const
    case "data_gate":
      return "idle" as const
    default:
      return "idle" as const
  }
}

export function GibeHonestyStrip({
  orgTraining,
  className,
  limit = 8,
}: {
  orgTraining: Record<string, MlAdminOrgModelStatus> | null | undefined
  className?: string
  limit?: number
}) {
  const { entries, counts } = summarizeOrgTraining(orgTraining)
  const shown = entries.slice(0, limit)

  return (
    <section
      className={cn("border border-border bg-card p-5 shadow-sm", RADIUS.panel, className)}
      data-gibe-honesty-strip=""
      aria-labelledby="gibe-honesty-heading"
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <p className={TYPE.eyebrow}>GIBE · Module C</p>
          <h2 id="gibe-honesty-heading" className={TYPE.sectionTitle}>
            Model runtime honesty
          </h2>
          <p className={cn(TYPE.bodyMuted, "mt-1 max-w-2xl")}>
            Live path from <span className="font-medium text-foreground">runtime_status</span> and
            artifact load — never the catalog{" "}
            <span className="font-medium text-foreground">TRAINED</span> label alone. Heuristic
            scores are estimates (STA-331).
          </p>
        </div>
        {entries.length > 0 ? (
          <div className="flex flex-wrap gap-2">
            {(Object.keys(COUNT_LABEL) as RuntimeHonestyKind[]).map((kind) =>
              counts[kind] > 0 ? (
                <StatusBadge key={kind} tone={toneFor(kind)} dot>
                  {counts[kind]} {COUNT_LABEL[kind]}
                </StatusBadge>
              ) : null,
            )}
          </div>
        ) : null}
      </div>

      {shown.length === 0 ? (
        <div
          className={cn(
            "mt-4 border border-dashed border-border bg-muted/30 px-4 py-8 text-center",
            RADIUS.card,
          )}
        >
          <Brain className="mx-auto h-8 w-8 text-muted-foreground" weight="duotone" aria-hidden />
          <p className={cn(TYPE.cardTitle, "mt-2")}>No runtime model status yet</p>
          <p className={cn(TYPE.meta, "mt-1 mx-auto max-w-md")}>
            When org training status is available, each model shows Estimate (heuristic), Model
            (artifact loaded), Insufficient data, or Catalog only — never a silent TRAINED claim.
          </p>
        </div>
      ) : (
        <ul className="mt-4 flex flex-wrap gap-2">
          {shown.map(({ name, presentation }) => (
            <li key={name}>
              <StatusBadge
                tone={presentation.statusTone}
                title={presentation.detail}
              >
                {formatStatusLabel(name)} · {presentation.label}
              </StatusBadge>
            </li>
          ))}
        </ul>
      )}

      <p className={cn(TYPE.meta, "mt-3")}>{CONFIDENCE_ESTIMATE_METHODOLOGY}</p>

      <div className="mt-3">
        <Button variant="link" size="sm" className="h-auto px-0" asChild>
          <Link href={APP_ROUTES.builtInModels}>View all models</Link>
        </Button>
      </div>
    </section>
  )
}
