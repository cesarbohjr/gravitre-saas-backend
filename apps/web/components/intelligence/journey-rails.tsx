"use client"

import Link from "next/link"
import { AlertTriangle, ArrowRight, Lightbulb, MousePointerClick } from "lucide-react"
import { AskPromptChips } from "@/components/gravitre/ask-prompt-chips"
import type { GravitreAISelectedEntity } from "@/components/gravitre/ai-workspace-provider"
import { APP_ROUTES } from "@/lib/app-routes"
import { readString } from "@/lib/intelligence/helpers"
import { buildLearningInsightMapHref } from "@/lib/intelligence/learning-map-focus"
import { cn } from "@/lib/utils"

type SignalRow = Record<string, unknown>
type Learning = { id: string; statement: string; learnedAt?: string }

const JOURNEY = ["Insight", "Evidence", "Relationship", "Expert graph"] as const

/** Where the operator is in Insight → Evidence → Relationship → Expert graph (G-STRUCT A5). */
export function IntelligenceJourney({ step, className }: { step: 0 | 1 | 2 | 3; className?: string }) {
  return (
    <ol className={cn("flex items-center gap-1 text-[11.5px]", className)} aria-label="Intelligence journey">
      {JOURNEY.map((label, index) => (
        <li key={label} className="flex items-center gap-1">
          <span
            aria-current={index === step ? "step" : undefined}
            className={cn(
              "inline-flex items-center gap-1.5 rounded-full px-2 py-0.5",
              index === step
                ? "bg-[color:var(--g-intelligence-soft)] font-semibold text-[color:var(--g-intelligence)]"
                : index < step
                  ? "text-foreground"
                  : "text-muted-foreground",
            )}
          >
            <span className="tabular-nums">{index + 1}</span>
            {label}
          </span>
          {index < JOURNEY.length - 1 ? <span className="text-muted-foreground/50" aria-hidden>›</span> : null}
        </li>
      ))}
    </ol>
  )
}

function RailHeading({ children, id }: { children: string; id: string }) {
  return (
    <h2 id={id} className="text-[12.5px] font-semibold text-foreground">
      {children}
    </h2>
  )
}

/** Left rail — what Gravitre surfaced: ranked signals and validated learnings. */
export function InsightRail({
  signals,
  signalsLoading,
  learnings,
  onSelectSignal,
}: {
  signals: SignalRow[]
  signalsLoading?: boolean
  learnings: Learning[]
  onSelectSignal: (signal: SignalRow) => void
}) {
  const top = [...signals]
    .sort((a, b) => Number(b.quality_score ?? 0) - Number(a.quality_score ?? 0))
    .slice(0, 4)

  return (
    <div className="space-y-5" data-testid="intel-insight-rail">
      <section aria-labelledby="insight-signals" className="space-y-1.5">
        <RailHeading id="insight-signals">Needs attention</RailHeading>
        {signalsLoading && top.length === 0 ? (
          <p className="text-xs text-muted-foreground">Loading signals…</p>
        ) : top.length === 0 ? (
          <p className="text-xs text-muted-foreground">Nothing ranked as urgent.</p>
        ) : (
          <ul className="-mx-2">
            {top.map((signal, index) => (
              <li key={readString(signal.id, String(index))}>
                <button
                  type="button"
                  onClick={() => onSelectSignal(signal)}
                  className="group flex w-full items-start gap-2 rounded-[8px] px-2 py-2 text-left transition-colors hover:bg-[color:var(--g-surface-1)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                >
                  <AlertTriangle className="mt-0.5 size-3.5 shrink-0 text-warning" aria-hidden />
                  <span className="min-w-0">
                    <span className="line-clamp-2 text-[12.5px] font-medium text-foreground">
                      {readString(signal.title, "Business signal")}
                    </span>
                    {readString(signal.summary, "") ? (
                      <span className="mt-0.5 line-clamp-1 text-[11.5px] text-muted-foreground">
                        {readString(signal.summary, "")}
                      </span>
                    ) : null}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section aria-labelledby="insight-learned" className="space-y-1.5">
        <div className="flex items-baseline justify-between gap-2">
          <RailHeading id="insight-learned">Learned</RailHeading>
          <Link href={APP_ROUTES.learning} className="text-[11.5px] font-medium text-[color:var(--g-brand)] hover:underline">
            Learning hub
          </Link>
        </div>
        {learnings.length === 0 ? (
          <p className="text-xs text-muted-foreground">No validated business learning yet.</p>
        ) : (
          <ul className="-mx-2">
            {learnings.slice(0, 4).map((row) => (
              <li key={row.id}>
                <Link
                  href={buildLearningInsightMapHref(row.id)}
                  className="flex items-start gap-2 rounded-[8px] px-2 py-2 transition-colors hover:bg-[color:var(--g-surface-1)]"
                >
                  <Lightbulb className="mt-0.5 size-3.5 shrink-0 text-[color:var(--g-intelligence)]" aria-hidden />
                  <span className="min-w-0">
                    <span className="line-clamp-2 text-[12.5px] text-foreground">{row.statement}</span>
                    {row.learnedAt ? (
                      <span className="mt-0.5 block text-[11px] text-muted-foreground">Learned {row.learnedAt}</span>
                    ) : null}
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  )
}

/** Right rail — evidence for the current selection, then measured outcomes. */
export function EvidenceRail({
  selected,
  totalEvents,
  avgConfidence,
  entityCount,
  relationshipCount,
}: {
  selected: GravitreAISelectedEntity | null
  totalEvents: number
  avgConfidence: number | null | undefined
  entityCount: number | null
  relationshipCount: number | null
}) {
  return (
    <div className="space-y-5" data-testid="intel-evidence-rail">
      <section aria-labelledby="evidence-selection" className="space-y-2">
        <RailHeading id="evidence-selection">Evidence</RailHeading>
        {selected ? (
          <div className="space-y-2 rounded-[12px] bg-[color:var(--g-intelligence-soft)] p-3">
            <p className="text-[11px] font-medium capitalize text-[color:var(--g-intelligence)]">{selected.kind}</p>
            <p className="line-clamp-2 text-[13px] font-semibold text-foreground">{selected.label}</p>
            <AskPromptChips
              layout="stack"
              className="-mx-2"
              prompts={[
                `Why does ${selected.label} matter right now?`,
                `What is ${selected.label} connected to?`,
              ]}
            />
          </div>
        ) : (
          <p className="flex items-start gap-2 rounded-[12px] border border-dashed border-[color:var(--g-border-default)] p-3 text-xs text-muted-foreground">
            <MousePointerClick className="mt-0.5 size-3.5 shrink-0" aria-hidden />
            Select a node, relationship or signal on the field to see the evidence behind it.
          </p>
        )}
      </section>

      <section aria-labelledby="evidence-measured" className="space-y-1">
        <RailHeading id="evidence-measured">Measured · 7 days</RailHeading>
        <dl className="divide-y divide-[color:var(--g-border-subtle)]">
          {[
            { label: "Outcome events", value: String(totalEvents) },
            { label: "Avg confidence", value: avgConfidence != null ? `${Math.round(avgConfidence * 100)}%` : "—" },
            { label: "Known entities", value: entityCount != null ? String(entityCount) : "—" },
            { label: "Relationships", value: relationshipCount != null ? String(relationshipCount) : "—" },
          ].map((row) => (
            <div key={row.label} className="flex items-center justify-between gap-3 py-1.5">
              <dt className="text-[12px] text-muted-foreground">{row.label}</dt>
              <dd className="text-[13px] font-semibold tabular-nums text-foreground">{row.value}</dd>
            </div>
          ))}
        </dl>
      </section>

      <section aria-labelledby="evidence-expert" className="space-y-1">
        <RailHeading id="evidence-expert">Go deeper</RailHeading>
        <ul className="-mx-2">
          {[
            { label: "Relationship graph", href: APP_ROUTES.learning },
            { label: "Department reports", href: APP_ROUTES.intelligenceReports },
            { label: "Predictions", href: APP_ROUTES.intelligencePredictive },
          ].map((link) => (
            <li key={link.href}>
              <Link
                href={link.href}
                className="group flex items-center justify-between rounded-[8px] px-2 py-1.5 text-[12.5px] text-foreground transition-colors hover:bg-[color:var(--g-surface-1)]"
              >
                {link.label}
                <ArrowRight className="size-3.5 text-muted-foreground transition-transform group-hover:translate-x-0.5" aria-hidden />
              </Link>
            </li>
          ))}
        </ul>
      </section>
    </div>
  )
}
