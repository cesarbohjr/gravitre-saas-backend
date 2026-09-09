"use client"

import Link from "next/link"
import { ArrowRight, Sparkles, Wrench, Shield, Zap } from "lucide-react"
import { MARKETING_COPY } from "@/lib/marketing-copy"
import { DivideX } from "@/components/marketing/nodus/divide"
import { MarketingPageHero, MarketingRails, MarketingPageEndCta } from "@/components/marketing/nodus/page-shell"
import {
  CHANGELOG_TRACE_STAGES,
  GravitreResolve,
  GravitreSection,
  GravitreSectionHeader,
  GravitreTrace,
  StageTraceVisual,
} from "@/components/marketing/system"

const releases = [
  ...MARKETING_COPY.changelog.releases,
  { version: "2.4.0", date: "April 5, 2026", title: "Multi-Agent Collaboration", description: "Coordinate multiple agents on complex tasks with defined roles. Each sub-agent completes its scoped work; results are aggregated after completion—not live shared memory.", type: "feature", highlights: ["Parallel sub-agent jobs via the agent queue", "Council-style aggregation of completed subtask results", "Collaboration graph in workflow builder", "Parallel job scheduling improvements"] },
  { version: "2.3.2", date: "March 28, 2026", title: "Security Enhancements", description: "Major security improvements with enhanced encryption, audit logging, and access controls for enterprise customers.", type: "security", highlights: ["Enhanced audit logging", "IP allowlisting for API access", "Session management improvements", "End-to-end encryption updates"] },
  { version: "2.3.0", date: "March 21, 2026", title: "Workflow Templates Library", description: "Pre-built workflow templates to help you get started faster.", type: "feature", highlights: ["Sales automation templates", "Marketing operations templates", "Finance and reporting templates", "One-click template deployment"] },
  { version: "2.2.5", date: "March 14, 2026", title: "Performance & Reliability", description: "Performance improvements and bug fixes across the platform.", type: "improvement", highlights: ["Workflow execution improvements", "Improved error recovery", "Better handling of large datasets", "Fixed: Connector sync issues"] },
  { version: "2.2.0", date: "March 7, 2026", title: "Advanced Scheduling", description: "New scheduling options including cron expressions, time zones, and calendar-aware triggers.", type: "feature", highlights: ["Cron expression support", "Time zone-aware scheduling", "Business day calendars", "Holiday-aware triggers"] },
  { version: "2.1.3", date: "February 28, 2026", title: "API v2 & New SDKs", description: "Introducing API v2 with improved consistency and new official SDKs.", type: "feature", highlights: ["REST API v2 with OpenAPI spec", "Official Node.js SDK", "Official Python SDK", "Webhook signature verification"] },
  { version: "2.0.0", date: "February 1, 2026", title: "AI Operator 2.0", description: "Major release with durable async operator analysis, ReAct-style reasoning when integrations are connected, and structured task outputs.", type: "major", highlights: ["Async operator analysis jobs", "ReAct-style reasoning on connected integrations", "Structured plans, findings, and recommended actions", "Conversation memory improvements", "Enhanced error handling", "Redesigned dashboard"] },
]

const getTypeIcon = (type: string) => {
  switch (type) {
    case "feature": return <Sparkles className="h-4 w-4" />
    case "improvement": return <Zap className="h-4 w-4" />
    case "security": return <Shield className="h-4 w-4" />
    case "major": return <Sparkles className="h-4 w-4" />
    default: return <Wrench className="h-4 w-4" />
  }
}

const getTypeColor = (type: string) => {
  switch (type) {
    // "major" is the marquee release — strongest emerald emphasis.
    case "major": return "bg-primary text-white border-emerald-600"
    case "feature": return "bg-primary/15 text-primary border-primary/20"
    // Neutral zinc keeps "improvement" distinct without adding an off-brand hue.
    case "improvement": return "bg-muted text-foreground border-border"
    // Amber is reserved for security/attention items.
    case "security": return "bg-amber-100 text-amber-700 border-amber-200"
    default: return "bg-muted text-muted-foreground border-border"
  }
}

export default function ChangelogPage() {
  return (
    <div className="bg-[color:var(--g-marketing-canvas)]">
      <MarketingPageHero
        badge="Changelog"
        title="Changelog"
        description={MARKETING_COPY.changelog.subtitle}
      >
        <div className="mt-6">
          <Link href="/roadmap" className="inline-flex items-center gap-2 text-sm text-primary hover:text-primary">
            View our roadmap
            <ArrowRight className="h-4 w-4" />
          </Link>
        </div>
      </MarketingPageHero>

      <DivideX />

      <GravitreSection>
        <GravitreSectionHeader
          align="center"
          badge="Release rhythm"
          title="Ship → Measure → Learn"
          description="How we ship — features land, we measure what changed, and we learn from what teams actually use."
          className="mb-6"
        />
        <GravitreTrace>
          <StageTraceVisual
            stages={CHANGELOG_TRACE_STAGES}
            gradientId="changelog-trace"
            ariaLabel="Changelog path from Ship through Measure to Learn"
          />
        </GravitreTrace>
      </GravitreSection>

      <DivideX />

      <MarketingRails>
        <div className="max-w-3xl mx-auto">
          <div className="relative">
            <div className="absolute left-0 md:left-24 top-0 bottom-0 w-px bg-muted" />
            <div className="space-y-12">
              {releases.map((release, i) => (
                <GravitreResolve key={release.version} delay={i * 0.08} className="relative pl-8 md:pl-36">
                  <div className="absolute left-0 md:left-24 top-0 -translate-x-1/2">
                    <div className={`flex h-8 w-8 items-center justify-center rounded-full border ${getTypeColor(release.type)}`}>{getTypeIcon(release.type)}</div>
                  </div>
                  <div className="absolute left-0 top-1 hidden md:block w-20 text-right">
                    <span className="text-xs text-muted-foreground">{release.date}</span>
                  </div>
                  <div className="rounded-xl border border-border bg-card p-6 shadow-sm">
                    <div className="flex flex-wrap items-center gap-3 mb-3">
                      <span className="text-xs font-mono text-primary bg-primary/15 px-2 py-1 rounded">v{release.version}</span>
                      <span className={`text-xs px-2 py-1 rounded border ${getTypeColor(release.type)}`}>{release.type.charAt(0).toUpperCase() + release.type.slice(1)}</span>
                      <span className="text-xs text-muted-foreground md:hidden">{release.date}</span>
                    </div>
                    <h3 className="text-lg font-medium text-foreground mb-2">{release.title}</h3>
                    <p className="text-sm text-muted-foreground mb-4">{release.description}</p>
                    <ul className="space-y-2">
                      {release.highlights.map((highlight) => (
                        <li key={highlight} className="flex items-start gap-2 text-sm text-muted-foreground"><span className="text-primary mt-1">-</span>{highlight}</li>
                      ))}
                    </ul>
                  </div>
                </GravitreResolve>
              ))}
            </div>
          </div>
        </div>
      </MarketingRails>

      <MarketingPageEndCta />
    </div>
  )
}
