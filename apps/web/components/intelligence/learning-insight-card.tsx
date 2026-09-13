"use client"

import Link from "next/link"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { TYPE } from "@/lib/design-system"
import { cn } from "@/lib/utils"
import type { LearningInsightDisplay } from "@/lib/intelligence/learning-insight-display"
import { buildLearningInsightMapHref } from "@/lib/intelligence/learning-map-focus"
import { MapTrifold } from "@phosphor-icons/react"

export function LearningInsightCard({ insight }: { insight: LearningInsightDisplay }) {
  const mapHref = buildLearningInsightMapHref(insight.id)
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-base font-medium leading-snug">{insight.statement}</CardTitle>
        {insight.learnedAtLabel ? (
          <p className={cn(TYPE.meta, "mt-1")}>Learned {insight.learnedAtLabel}</p>
        ) : null}
      </CardHeader>
      <CardContent className="space-y-3 text-sm text-muted-foreground">
        {insight.learnedFrom.length > 0 ? (
          <div>
            <p className={TYPE.eyebrow}>Learned from</p>
            <p>{insight.learnedFrom.join(" · ")}</p>
          </div>
        ) : null}
        {insight.evidence.length > 0 ? (
          <div>
            <p className={TYPE.eyebrow}>Evidence</p>
            <ul className="mt-1 space-y-1">
              {insight.evidence.map((line) => (
                <li
                  key={line}
                  className="rounded-md border border-divide bg-[color:var(--g-surface-2)]/50 px-2 py-1 text-xs"
                >
                  {line}
                </li>
              ))}
            </ul>
          </div>
        ) : null}
        {insight.affectedEntities.length > 0 ? (
          <p>
            <span className={TYPE.eyebrow}>Entities: </span>
            {insight.affectedEntities.join(", ")}
          </p>
        ) : null}
        {insight.resultingChanges.length > 0 ? (
          <p>
            <span className={TYPE.eyebrow}>Changes: </span>
            {insight.resultingChanges.join("; ")}
          </p>
        ) : null}
        {insight.provenance ? (
          <p className={cn(TYPE.meta, "border-t border-divide pt-2")}>Source: {insight.provenance}</p>
        ) : null}
        <Link
          href={mapHref}
          className="inline-flex items-center gap-1.5 text-xs font-medium text-[color:var(--g-brand)] hover:underline"
        >
          <MapTrifold className="h-3.5 w-3.5" aria-hidden />
          View on intelligence map
        </Link>
      </CardContent>
    </Card>
  )
}
