"use client"

/**
 * Canonical BusinessOutcome renderer.
 * Zero business logic — displays exactly what the DTO provides.
 * Shared by chat, timeline, Activity, and export preview surfaces.
 *
 * Four honest presentation states derived from DTO fields only:
 * `status` + `sections.verification` (verified / reviewState / finding).
 */

import { createContext, useContext, useState, type ReactNode } from "react"
import Link from "next/link"
import {
  ArrowRight,
  ArrowUpRight,
  CheckCircle2,
  ChevronDown,
  CircleDashed,
  Flag,
  ShieldAlert,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible"
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
    impact?: string
    evidence?: {
      links?: Array<{ label: string; href: string; kind?: string }>
      entityType?: string | null
      entityId?: string | null
      integration?: string | null
    }
    verification?: {
      verified?: boolean
      method?: string
      detail?: string | null
      reviewState?: string | null
      checkFailed?: string | null
      finding?: string | null
      nextActions?: string[] | null
    }
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
 * Four honest presentation states, all derived from DTO fields:
 * - failed:   the action did not happen (destructive).
 * - flagged:  Phase 4 degenerate batch (or review_state) — calm concern, not failure.
 * - verified: it happened AND was independently verified (success).
 * - unproven: it happened but carries no verification proof — calm/neutral.
 */
type OutcomeState = "verified" | "unproven" | "failed" | "flagged"

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
    pillLabel: "Verified",
  },
  unproven: {
    icon: CircleDashed,
    iconClass: "text-muted-foreground",
    accent: "border-l-border",
    surface: "border-border/80",
    pillClass: "bg-muted text-muted-foreground ring-1 ring-inset ring-border",
    pillLabel: "Not verified",
  },
  flagged: {
    icon: Flag,
    iconClass: "text-warning",
    accent: "border-l-warning",
    // Opaque tint mixed into the real card color (not bg-warning/[0.04] over
    // transparent) — flagged carries the most text (finding + next actions)
    // of any state, so it is the worst one to leave translucent over the
    // mesh chat backgrounds. See card surface logic below.
    surface: "border-warning/30 bg-[color-mix(in_oklch,var(--warning)_6%,var(--card))]",
    pillClass: "bg-warning/15 text-warning ring-1 ring-inset ring-warning/25",
    pillLabel: "Flagged for review",
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

function resolveOutcomeState(outcome: BusinessOutcomeDto): OutcomeState {
  const status = (outcome.status || "").toLowerCase()
  const reviewState = (outcome.sections?.verification?.reviewState || "").toLowerCase()
  if (status === "failed") return "failed"
  if (status === "flagged_for_review" || reviewState === "flagged_for_review") return "flagged"
  if (outcome.sections?.verification?.verified === true) return "verified"
  return "unproven"
}

function isExternal(href: string): boolean {
  return href.startsWith("http://") || href.startsWith("https://")
}

/**
 * Collapsing is opt-in per surface. Chat cards and the export preview must keep
 * rendering every section expanded (a printed audit trail can't hide behind a
 * disclosure), so only the `timeline` density turns this on.
 */
const SectionCollapseContext = createContext(false)

function Section({
  title,
  children,
  /** Ignored unless the surrounding density enabled collapsing. */
  defaultOpen = true,
  /**
   * Short summary pinned to the trigger (e.g. "4 steps"). Collapsing must not
   * hide *whether* a section has content — only the content itself.
   */
  meta,
}: {
  title: string
  children: ReactNode
  defaultOpen?: boolean
  meta?: string
}) {
  const collapsible = useContext(SectionCollapseContext)
  const [open, setOpen] = useState(defaultOpen)

  if (!collapsible) {
    return (
      <div className="mt-3">
        <p className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">{title}</p>
        <div className="mt-1 text-xs text-foreground/90">{children}</div>
      </div>
    )
  }

  return (
    <Collapsible open={open} onOpenChange={setOpen} className="mt-2 border-t border-border/50 pt-2">
      <CollapsibleTrigger className="group flex w-full items-center gap-1.5 rounded text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
        <ChevronDown
          className={cn(
            "h-3 w-3 shrink-0 text-muted-foreground transition-transform duration-200",
            !open && "-rotate-90",
          )}
          aria-hidden
        />
        <span className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground group-hover:text-foreground">
          {title}
        </span>
        {meta ? (
          <span className="ml-auto shrink-0 text-[10px] tabular-nums text-muted-foreground">{meta}</span>
        ) : null}
      </CollapsibleTrigger>
      {/* collapsible-* (not accordion-*) — Radix only publishes
          --radix-collapsible-content-height here; the accordion keyframes would
          animate to `auto` and jump. */}
      <CollapsibleContent className="overflow-hidden data-[state=closed]:animate-collapsible-up data-[state=open]:animate-collapsible-down">
        <div className="mt-1 text-xs text-foreground/90">{children}</div>
      </CollapsibleContent>
    </Collapsible>
  )
}

export function BusinessOutcomeView({ outcome, className, density = "chat" }: Props) {
  const sections = outcome.sections || {}
  const state = resolveOutcomeState(outcome)
  const style = STATE_STYLES[state]
  const Icon = style.icon
  const verification = sections.verification
  // Only the inspector surface collapses; chat and export stay fully expanded.
  const collapsibleSections = density === "timeline"

  return (
    <SectionCollapseContext.Provider value={collapsibleSections}>
    <div
      className={cn(
        // Solid card surface so the evidence receipt stays fully legible on top
        // of the 8 translucent mesh chat backgrounds. `flagged`'s `style.surface`
        // supplies its own OPAQUE color-mix('--warning' into '--card') background,
        // so it must not also receive the plain `bg-card` utility below — two
        // background-color utilities on one element race by CSS source order,
        // not class-string order, which previously let a transparent
        // `bg-warning/[0.04]` win and show the mesh straight through the
        // flagged card's text.
        "rounded-lg border px-3.5 py-3 text-sm shadow-sm",
        style.surface,
        density === "export"
          ? "bg-background border-l-0"
          : state === "flagged"
            ? ""
            : "bg-card",
        density === "chat" && "border-l-2",
        density === "chat" && style.accent,
        density === "timeline" && "rounded-md",
        density === "timeline" && state === "flagged" && "border-l-2 border-l-warning",
        className,
      )}
      data-business-outcome-id={outcome.id}
      data-projection={outcome.projection || "business_outcome"}
      data-lifecycle={outcome.lifecycleState}
      data-outcome-state={state}
      data-check-failed={verification?.checkFailed || undefined}
    >
      <div className="flex items-start gap-2">
        <Icon className={cn("mt-0.5 h-4 w-4 shrink-0", style.iconClass)} />
        <div className="min-w-0 flex-1">
          {/* Header: title + glanceable verification status. Requirement #1 —
              a user should register "this really happened, here's proof" before
              reading any detail, so status is a pill up here, not buried below. */}
          <div
            className={cn(
              "flex items-start justify-between gap-2",
              // In the inspector the card scrolls inside a fixed-height pane, so
              // pin the identity of what you're reading to the top.
              collapsibleSections && "sticky top-0 z-10 -mx-0.5 bg-card/95 px-0.5 py-0.5 backdrop-blur-sm",
            )}
          >
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
            {[outcome.kind, outcome.status, outcome.lifecycleState]
              .filter(Boolean)
              .map((raw) => String(raw).replace(/[_-]+/g, " ").trim())
              .join(" · ")}
          </p>

          {/* Evidence — the real vendor link. Requirement #1 elevates this to the
              top of the body and gives external (vendor) links a filled CTA so
              the proof is the most prominent action; internal links stay outline. */}
          {sections.evidence?.links?.length ? (
            <Section title="Evidence">
              <div className="flex flex-wrap gap-2">
                {sections.evidence.links.map((link) => {
                  const external = isExternal(link.href)
                  // Never render a filled/primary CTA on a Failed card — a
                  // confident-looking button under "did not happen" reads as
                  // success next to the red rail. Failed always gets outline.
                  const filled = external && state !== "failed"
                  return (
                    <Button
                      key={`${link.href}-${link.label}`}
                      asChild
                      size="sm"
                      variant={filled ? "default" : "outline"}
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
            <Section title="Explanation" defaultOpen={false}>
              <p className="whitespace-pre-wrap">{sections.explanation}</p>
            </Section>
          ) : null}

          {verification ? (
            <Section title="Verification" defaultOpen={state === "flagged"}>
              <p>
                {state === "flagged"
                  ? "Flagged for review"
                  : verification.verified
                    ? "Verified"
                    : "Not verified"}
                {verification.method ? ` · ${verification.method}` : ""}
                {verification.checkFailed ? ` · check: ${verification.checkFailed}` : ""}
              </p>
              {verification.finding ? (
                <p className="mt-1 font-medium text-foreground/90">{verification.finding}</p>
              ) : null}
              {verification.detail ? (
                <p className="mt-0.5 text-muted-foreground">{verification.detail}</p>
              ) : null}
              {verification.nextActions?.length ? (
                <ul className="mt-2 list-disc space-y-1 pl-4 text-muted-foreground">
                  {verification.nextActions.map((action) => (
                    <li key={action}>{action}</li>
                  ))}
                </ul>
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
              <Section
                title="Execution proof"
                defaultOpen={false}
                meta={`${entries.length} field${entries.length === 1 ? "" : "s"}`}
              >
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
            <Section
              title="Timeline"
              defaultOpen={false}
              meta={`${sections.timeline.length} step${sections.timeline.length === 1 ? "" : "s"}`}
            >
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
            <Section title="Approval" defaultOpen={false} meta={sections.approval.status}>
              <p>
                {sections.approval.status}
                {sections.approval.required != null
                  ? ` · ${sections.approval.received ?? 0}/${sections.approval.required}`
                  : ""}
              </p>
            </Section>
          ) : null}

          {sections.recommendations?.length ? (
            <Section
              title="Recommendations"
              defaultOpen={false}
              meta={`${sections.recommendations.length}`}
            >
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
            <Section
              title="Diff"
              defaultOpen={false}
              meta={sections.diff.available ? "available" : "none"}
            >
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
            <Section
              title="Undo"
              defaultOpen={false}
              meta={sections.undo.available ? "available" : "unavailable"}
            >
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
    </SectionCollapseContext.Provider>
  )
}
