"use client"

/**
 * Canonical BusinessOutcome renderer.
 * Zero business logic — displays exactly what the DTO provides.
 * Shared by chat, timeline, and export preview surfaces.
 *
 * Presentation pass (preview-fidelity handoff, Surface 1): this file changed
 * ONLY visually. No DTO field, no copy substance, and no link target was
 * altered. The three status treatments below are all derived from fields the
 * DTO already carries (`status` + `sections.verification.verified`).
 */

import type { ReactNode } from "react"
import Link from "next/link"
import { ArrowRight, ArrowUpRight, CheckCircle2, CircleDashed, ShieldAlert } from "lucide-react"
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

/**
 * Three honest presentation states, all derived from existing DTO fields:
 * - failed:   the action did not happen (destructive).
 * - verified: it happened AND was independently verified (success).
 * - unproven: it happened but carries no verification proof — shown calm and
 *             neutral rather than a false-alarm amber, matching the product's
 *             honesty language without overstating or panicking.
 */
type OutcomeState = "verified" | "unproven" | "failed"

const STATE_STYLES: Record<
  OutcomeState,
  {
    icon: typeof CheckCircle2
    iconClass: string
    accent: string
    surface: string
    pillClass: string
    pillLabel: string
  }
> = {
  verified: {
    icon: CheckCircle2,
    iconClass: "text-success",
    accent: "border-l-success",
    surface: "border-success/25",
    pillClass: "bg-success/10 text-success ring-1 ring-inset ring-success/20",
    // Existing card string, reused verbatim.
    pillLabel: "Verified",
  },
  unproven: {
    icon: CircleDashed,
    iconClass: "text-muted-foreground",
    accent: "border-l-border",
    surface: "border-border/80",
    pillClass: "bg-muted text-muted-foreground ring-1 ring-inset ring-border",
    // Existing card string, reused verbatim.
    pillLabel: "Not verified",
  },
  failed: {
    icon: ShieldAlert,
    iconClass: "text-destructive",
    accent: "border-l-destructive",
    surface: "border-destructive/25",
    pillClass: "bg-destructive/10 text-destructive ring-1 ring-inset ring-destructive/20",
    pillLabel: "Failed",
  },
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
  const verified = !failed && sections.verification?.verified === true
  const state: OutcomeState = failed ? "failed" : verified ? "verified" : "unproven"
  const style = STATE_STYLES[state]
  const Icon = style.icon

  return (
    <div
      className={cn(
        // Solid card surface so the evidence receipt stays fully legible on top
        // of the 8 translucent mesh chat backgrounds (previously semi-transparent
        // and washed out against them).
        "rounded-lg border px-3.5 py-3 text-sm shadow-sm",
        style.surface,
        density === "export" ? "bg-background border-l-0" : "bg-card",
        density === "chat" && "border-l-2",
        density === "chat" && style.accent,
        density === "timeline" && "rounded-md",
        className,
      )}
      data-business-outcome-id={outcome.id}
      data-projection={outcome.projection || "business_outcome"}
      data-lifecycle={outcome.lifecycleState}
      data-outcome-state={state}
    >
      <div className="flex items-start gap-2">
        <Icon className={cn("mt-0.5 h-4 w-4 shrink-0", style.iconClass)} />
        <div className="min-w-0 flex-1">
          {/* Header: title + glanceable verification status. Requirement #1 —
              a user should register "this really happened, here's proof" before
              reading any detail, so status is a pill up here, not buried below. */}
          <div className="flex items-start justify-between gap-2">
            <p className="min-w-0 break-words font-medium text-foreground">{outcome.title || "Outcome"}</p>
            <span
              className={cn(
                "mt-0.5 shrink-0 rounded-full px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide",
                style.pillClass,
              )}
            >
              {style.pillLabel}
            </span>
          </div>
          <p className="mt-0.5 text-[11px] text-muted-foreground">
            {[outcome.kind, outcome.status, outcome.lifecycleState].filter(Boolean).join(" · ")}
          </p>

          {/* Evidence — the real vendor link. Requirement #1 elevates this to the
              top of the body and gives external (vendor) links a filled CTA so
              the proof is the most prominent action; internal links stay outline. */}
          {sections.evidence?.links?.length ? (
            <Section title="Evidence">
              <div className="flex flex-wrap gap-2">
                {sections.evidence.links.map((link) => {
                  const external = isExternal(link.href)
                  return (
                    <Button
                      key={`${link.href}-${link.label}`}
                      asChild
                      size="sm"
                      variant={external ? "default" : "outline"}
                      className="h-8 text-xs"
                    >
                      {external ? (
                        <a href={link.href} target="_blank" rel="noopener noreferrer">
                          {link.label}
                          <ArrowUpRight className="ml-1.5 h-3 w-3" />
                        </a>
                      ) : (
                        <Link href={link.href}>
                          {link.label}
                          <ArrowRight className="ml-1.5 h-3 w-3" />
                        </Link>
                      )}
                    </Button>
                  )
                })}
              </div>
            </Section>
          ) : null}

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

          {(() => {
            const args = sections.metadata?.actionArgs
            if (!args || typeof args !== "object" || Array.isArray(args)) return null
            const entries = Object.entries(args as Record<string, unknown>).filter(
              ([, value]) => value != null && String(value).trim() !== "",
            )
            if (!entries.length) return null
            return (
              <Section title="Execution proof">
                <dl className="space-y-1">
                  {entries.map(([key, value]) => (
                    <div key={key} className="flex gap-2">
                      <dt className="shrink-0 font-medium text-foreground/80">{key}</dt>
                      <dd className="min-w-0 break-words text-muted-foreground">{String(value)}</dd>
                    </div>
                  ))}
                </dl>
              </Section>
            )
          })()}

          {sections.timeline?.length ? (
            <Section title="Timeline">
              <ol className="space-y-2">
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
                      {step.evidenceUrl ? (
                        <p className="mt-1">
                          {isExternal(step.evidenceUrl) ? (
                            <a
                              href={step.evidenceUrl}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="inline-flex items-center gap-1 text-[11px] font-medium text-foreground underline-offset-2 hover:underline"
                            >
                              Open completed work
                              <ArrowRight className="h-3 w-3" />
                            </a>
                          ) : (
                            <Link
                              href={step.evidenceUrl}
                              className="inline-flex items-center gap-1 text-[11px] font-medium text-foreground underline-offset-2 hover:underline"
                            >
                              Open completed work
                              <ArrowRight className="h-3 w-3" />
                            </Link>
                          )}
                        </p>
                      ) : null}
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
                <div key={rec.title} className="mt-1 rounded-lg border border-border/60 bg-muted/30 px-2.5 py-2">
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
