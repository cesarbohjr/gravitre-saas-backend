"use client"

/**
 * Intelligence hub readiness strip — signal counts from training-readiness only.
 * No TRAINED badges, prices, or entitlement toggles.
 */

import Link from "next/link"
import { Button } from "@/components/ui/button"
import { GravitreMetric } from "@/components/gravitre/nodus-product"
import { APP_ROUTES, LEGACY_APP_ROUTES } from "@/lib/app-routes"
import { TYPE } from "@/lib/design-system"
import { readString } from "@/lib/intelligence/helpers"
import { cn } from "@/lib/utils"
import { ArrowRight, Database, Pulse } from "@phosphor-icons/react"

export function summarizeTrainingReadiness(readiness: Record<string, unknown> | null | undefined): {
  ready: number
  needsData: number
  recent: number
  other: number
  total: number
} {
  const byModel = (readiness?.by_model as Record<string, Record<string, unknown>> | undefined) ?? {}
  let ready = 0
  let needsData = 0
  let recent = 0
  let other = 0
  for (const info of Object.values(byModel)) {
    const status = readString(info?.status, "").toLowerCase()
    if (status === "ready") ready += 1
    else if (status === "insufficient_data") needsData += 1
    else if (status === "already_trained_recently") recent += 1
    else other += 1
  }
  return {
    ready,
    needsData,
    recent,
    other,
    total: Object.keys(byModel).length,
  }
}

export function TrainingReadinessStrip({
  readiness,
  className,
  loading = false,
}: {
  readiness: Record<string, unknown> | null | undefined
  className?: string
  loading?: boolean
}) {
  const summary = summarizeTrainingReadiness(readiness)

  return (
    <section
      className={cn(
        "rounded-[var(--np-radius-lg)] border border-divide bg-[color:var(--g-surface-1)] p-5 shadow-[var(--np-shadow)]",
        className,
      )}
      aria-labelledby="training-readiness-heading"
      data-training-readiness-strip=""
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <p className={TYPE.eyebrow}>Training signals</p>
          <h2 id="training-readiness-heading" className={TYPE.sectionTitle}>
            Model data readiness
          </h2>
          <p className={cn(TYPE.bodyMuted, "mt-1 max-w-2xl")}>
            Counts from org signal thresholds only — ready to train, still gathering examples, or
            recently trained (cooldown). Not a TRAINED badge or entitlement claim.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button variant="outline" size="sm" asChild>
            <Link href={LEGACY_APP_ROUTES.intelligenceModelsPath}>
              Built-in models
              <ArrowRight className="ml-1 h-3.5 w-3.5" aria-hidden />
            </Link>
          </Button>
          <Button variant="outline" size="sm" asChild>
            <Link href={APP_ROUTES.training}>
              Training
              <ArrowRight className="ml-1 h-3.5 w-3.5" aria-hidden />
            </Link>
          </Button>
        </div>
      </div>

      {loading && !readiness ? (
        <p className={cn(TYPE.meta, "mt-4")}>Loading readiness signals…</p>
      ) : summary.total === 0 ? (
        <p className={cn(TYPE.meta, "mt-4 rounded-[var(--np-radius-md)] border border-dashed border-divide bg-[color:var(--g-surface-2)]/50 px-3 py-3")}>
          No training-readiness rows yet for this org. Open built-in models or Training once signal
          collectors have run.
        </p>
      ) : (
        <div className="mt-4 grid grid-cols-2 gap-[var(--np-kpi-gap)] sm:grid-cols-4">
          <GravitreMetric
            label="Ready"
            value={summary.ready}
            hint="Threshold met"
            icon={<Pulse className="h-4 w-4" weight="duotone" aria-hidden />}
          />
          <GravitreMetric
            label="Needs data"
            value={summary.needsData}
            hint="Below threshold"
            warning={summary.needsData > 0}
            icon={<Database className="h-4 w-4" weight="duotone" aria-hidden />}
          />
          <GravitreMetric
            label="Recent train"
            value={summary.recent}
            hint="In cooldown"
          />
          <GravitreMetric
            label="Tracked"
            value={summary.total}
            hint="Models with signals"
          />
        </div>
      )}
    </section>
  )
}
