"use client"

/**
 * Canonical BusinessOutcome renderer.
 * Zero business logic — displays exactly what the DTO provides.
 * Shared by chat, timeline, and export preview surfaces.
 */

import type { ReactNode } from "react"
import Link from "next/link"
import { ArrowRight, CheckCircle2, ShieldAlert } from "lucide-react"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"

export type BusinessOutcomeDto = {
  id: string
  orgId?: string
  kind?: string
  title?: string
  status?: string
  lifecycleState?: string
  lifecycleStatesReached?: string[]
  source?: string | null
  createdAt?: string | null
  sections?: {
    summary?: string
    evidence?: {
      links?: Array<{ label: string; href: string; kind?: string }>
      entityType?: string | null
      entityId?: string | null
      integration?: string | null
    }
    verification?: { verified?: boolean; method?: string; detail?: string | null }
    explanation?: string
    timeline?: Array<{
      index?: number
      label?: string
      status?: string
      summary?: string | null
      evidenceUrl?: string | null
      agentName?: string | null
    }>
    recommendations?: Array<{
      title?: string
      reason?: string
      suggestedUtterance?: string | null
      advisoryOnly?: boolean
      href?: string | null
      confidence?: number | null
      confidenceIsEstimate?: boolean
    }>
    approval?: { status?: string; required?: number | null; received?: number | null }
    diff?: { available?: boolean; prior?: Record<string, unknown> | null; note?: string | null }
    undo?: {
      available?: boolean
      compensatingAction?: string | null
      honestUnavailableReason?: string | null
    }
    metadata?: Record<string, unknown> | null
  }
  pipelineStagesCompleted?: string[]
  runId?: string | null
  conversationId?: string | null
  projection?: string
  advisoryOnlyRecommendations?: boolean
}

type Props = {
  outcome: BusinessOutcomeDto
  className?: string
  /** Presentation-only density; does not change business content. */
  density?: "chat" | "timeline" | "export"
}

function isExternal(href: string): boolean {
  return href.startsWith("http://") || href.startsWith("https://")
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="mt-3">
      <p className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">{title}</p>
      <div className="mt-1 text-xs text-foreground/90">{children}</div>
    </div>
  )
}

export function BusinessOutcomeView({ outcome, className, density = "chat" }: Props) {
  const sections = outcome.sections || {}
  const failed = (outcome.status || "").toLowerCase() === "failed"
  const Icon = failed ? ShieldAlert : CheckCircle2

  return (
    <div
      className={cn(
        "rounded-lg border px-3.5 py-3 text-sm",
        failed
          ? "border-red-500/20 bg-red-500/[0.04]"
          : "border-border/80 bg-background/70 dark:bg-card/50",
        density === "chat" && !failed && "border-l-2 border-l-emerald-600/50 dark:border-l-emerald-400/40",
        density === "chat" && failed && "border-l-2 border-l-red-500/50",
        density === "timeline" && "rounded-md",
        density === "export" && "border-border bg-background border-l-0",
        className,
      )}
      data-business-outcome-id={outcome.id}
      data-projection={outcome.projection || "business_outcome"}
      data-lifecycle={outcome.lifecycleState}
    >
      <div className="flex items-start gap-2">
        <Icon
          className={cn(
            "mt-0.5 h-4 w-4 shrink-0",
            failed ? "text-red-600" : "text-emerald-600",
          )}
        />
        <div className="min-w-0 flex-1">
          <p className="break-words font-medium text-foreground">{outcome.title || "Outcome"}</p>
          <p className="mt-0.5 text-[11px] text-muted-foreground">
            {[outcome.kind, outcome.status, outcome.lifecycleState].filter(Boolean).join(" · ")}
          </p>

          {sections.summary ? (
            <Section title="Summary">
              <p className="whitespace-pre-wrap">{sections.summary}</p>
            </Section>
          ) : null}

          {sections.explanation ? (
            <Section title="Explanation">
              <p className="whitespace-pre-wrap">{sections.explanation}</p>
            </Section>
          ) : null}

          {sections.verification ? (
            <Section title="Verification">
              <p>
                {sections.verification.verified ? "Verified" : "Not verified"}
                {sections.verification.method ? ` · ${sections.verification.method}` : ""}
              </p>
              {sections.verification.detail ? (
                <p className="mt-0.5 text-muted-foreground">{sections.verification.detail}</p>
              ) : null}
            </Section>
          ) : null}

          {sections.evidence?.links?.length ? (
            <Section title="Evidence">
              <div className="flex flex-wrap gap-2">
                {sections.evidence.links.map((link) => (
                  <Button key={`${link.href}-${link.label}`} asChild size="sm" variant="outline" className="h-7 text-xs">
                    {isExternal(link.href) ? (
                      <a href={link.href} target="_blank" rel="noopener noreferrer">
                        {link.label}
                        <ArrowRight className="ml-1.5 h-3 w-3" />
                      </a>
                    ) : (
                      <Link href={link.href}>
                        {link.label}
                        <ArrowRight className="ml-1.5 h-3 w-3" />
                      </Link>
                    )}
                  </Button>
                ))}
              </div>
            </Section>
          ) : null}

          {sections.timeline?.length ? (
            <Section title="Timeline">
              <ol className="space-y-1.5">
                {sections.timeline.map((step) => (
                  <li key={step.index ?? step.label} className="flex gap-2">
                    <span className="font-medium text-foreground/80">{step.index}.</span>
                    <span className="min-w-0 flex-1">
                      <span className="text-foreground/90">
                        {step.label}
                        {step.agentName ? ` · ${step.agentName}` : ""}
                        {step.status ? ` (${step.status})` : ""}
                      </span>
                      {step.summary ? <p className="mt-0.5 text-muted-foreground">{step.summary}</p> : null}
                    </span>
                  </li>
                ))}
              </ol>
            </Section>
          ) : null}

          {sections.approval ? (
            <Section title="Approval">
              <p>
                {sections.approval.status}
                {sections.approval.required != null
                  ? ` · ${sections.approval.received ?? 0}/${sections.approval.required}`
                  : ""}
              </p>
            </Section>
          ) : null}

          {sections.recommendations?.length ? (
            <Section title="Recommendations">
              {sections.recommendations.map((rec) => (
                <div key={rec.title} className="mt-1 rounded-lg border border-border/60 bg-background/60 px-2.5 py-2">
                  <p className="font-medium">{rec.title}</p>
                  {rec.reason ? <p className="mt-0.5 text-muted-foreground">{rec.reason}</p> : null}
                  {rec.suggestedUtterance ? (
                    <p className="mt-1 text-foreground/80">
                      Suggest only — say &ldquo;{rec.suggestedUtterance}&rdquo; to proceed.
                    </p>
                  ) : null}
                  {rec.confidenceIsEstimate ? (
                    <p className="mt-0.5 text-[10px] text-muted-foreground">Confidence is an estimate</p>
                  ) : null}
                </div>
              ))}
            </Section>
          ) : null}

          {sections.diff ? (
            <Section title="Diff">
              {sections.diff.available && sections.diff.prior ? (
                <pre className="overflow-x-auto rounded bg-muted/40 p-2 text-[10px]">
                  {JSON.stringify(sections.diff.prior, null, 2)}
                </pre>
              ) : (
                <p className="text-muted-foreground">{sections.diff.note || "No prior value available."}</p>
              )}
            </Section>
          ) : null}

          {sections.undo ? (
            <Section title="Undo">
              {sections.undo.available ? (
                <p>
                  Compensating action available
                  {sections.undo.compensatingAction ? `: ${sections.undo.compensatingAction}` : ""}
                </p>
              ) : (
                <p className="text-muted-foreground">
                  {sections.undo.honestUnavailableReason || "Undo is not available for this action."}
                </p>
              )}
            </Section>
          ) : null}

          {density !== "chat" && outcome.pipelineStagesCompleted?.length ? (
            <p className="mt-3 text-[10px] text-muted-foreground">
              Pipeline: {outcome.pipelineStagesCompleted.join(" → ")}
            </p>
          ) : null}
        </div>
      </div>
    </div>
  )
}
