"use client"

import Link from "next/link"
import { ArrowRight, CheckCircle2, Circle, Clock } from "lucide-react"
import { DivideX } from "@/components/marketing/nodus/divide"
import {
  MarketingPageEndCta,
  MarketingPageHero,
  MarketingRails,
} from "@/components/marketing/nodus/page-shell"
import {
  GravitreFlow,
  GravitreReveal,
  GravitreResolve,
  GravitreSection,
  GravitreSectionHeader,
  GravitreTrace,
  GsapSiteStorySticky,
  ROADMAP_TRACE_STAGES,
  StageTraceVisual,
} from "@/components/marketing/system"

const roadmapItems = {
  shipped: [
    {
      title: "Multi-Agent Collaboration",
      description: "Agents can work together on complex tasks with shared context",
    },
    {
      title: "Workflow Templates Library",
      description: "Reusable templates for common automation use cases",
    },
    {
      title: "Advanced Security Controls",
      description: "Enhanced access controls and audit capabilities",
    },
    {
      title: "Advanced Scheduling",
      description: "Cron expressions, time zones, and calendar-aware triggers",
    },
  ],
  inProgress: [
    {
      title: "Natural Language Workflow Builder",
      description: "Build workflows by describing them in plain English",
    },
    {
      title: "Custom LLM Integration",
      description: "Bring your own LLM (OpenAI, Anthropic, etc.)",
    },
    {
      title: "Mobile App",
      description: "Monitor and manage workflows from iOS and Android",
    },
  ],
  planned: [
    {
      title: "Visual Agent Builder",
      description: "Drag-and-drop interface for creating custom agents",
    },
    {
      title: "Data Warehouse Connectors",
      description: "Direct connections to Snowflake, BigQuery, Databricks",
    },
    {
      title: "Agent Marketplace",
      description: "Community-built agents and workflows",
    },
    {
      title: "Self-Hosted Option",
      description: "Deploy Gravitre in your own infrastructure",
    },
    {
      title: "Zapier/Make Integration",
      description: "Use Gravitre as a step in Zapier or Make workflows",
    },
  ],
  exploring: [
    {
      title: "Voice Commands",
      description: "Control Gravitre with voice through integrations",
    },
    {
      title: "Real-time Collaboration",
      description: "Multiple users editing workflows simultaneously",
    },
    {
      title: "AI-Powered Debugging",
      description: "AI assistant to help troubleshoot workflow issues",
    },
  ],
}

const StatusBadge = ({ status }: { status: string }) => {
  const styles = {
    shipped: "bg-primary/15 text-primary border-primary/20",
    inProgress: "bg-amber-100 text-amber-700 border-amber-200",
    planned: "bg-muted text-charcoal border-border",
    exploring: "bg-muted text-charcoal border-border",
  }
  const labels = {
    shipped: "Shipped",
    inProgress: "In progress",
    planned: "Planned",
    exploring: "Exploring",
  }
  return (
    <span className={`text-xs px-2 py-1 rounded border ${styles[status as keyof typeof styles]}`}>
      {labels[status as keyof typeof labels]}
    </span>
  )
}

export default function RoadmapPage() {
  return (
    <div className="bg-[color:var(--g-marketing-canvas)]">
      <MarketingPageHero
        badge="Roadmap"
        title="Product Roadmap"
        description="See what we're building and what's next for Gravitre — status labels only, no vote theater."
      >
        <div className="mt-8 flex flex-col sm:flex-row items-center justify-center gap-4">
          <a
            href="mailto:product@gravitre.app?subject=Gravitre%20feature%20suggestion"
            className="inline-flex items-center gap-2 rounded-full bg-foreground px-6 py-3 text-sm font-medium text-white transition-all hover:bg-foreground/90"
          >
            Suggest a feature
            <ArrowRight className="h-4 w-4" />
          </a>
          <Link
            href="/changelog"
            className="inline-flex items-center gap-2 text-sm text-primary hover:text-primary"
          >
            View changelog
            <ArrowRight className="h-4 w-4" />
          </Link>
        </div>
      </MarketingPageHero>

      <DivideX />

      <GravitreSection>
        <GravitreSectionHeader
          align="center"
          badge="Site story"
          title="Connect → Understand → Coordinate → Act → Verify → Learn"
          description="One signature TRACE — the spine behind what we ship and what comes next."
          className="mb-6"
        />
        <GravitreTrace>
          <StageTraceVisual
            stages={ROADMAP_TRACE_STAGES}
            gradientId="roadmap-trace"
            ariaLabel="Roadmap path from Connect through Understand, Coordinate, Act, Verify, to Learn"
            caption="Connect → Learn — pinned GSAP ScrollTrigger narrative below (reduced-motion uses a static grid)."
          />
        </GravitreTrace>
      </GravitreSection>

      <DivideX />

      <GsapSiteStorySticky />

      <DivideX />

      <MarketingRails className="py-8">
        <div className="flex flex-wrap items-center justify-center gap-4">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="h-4 w-4 text-primary" />
            <span className="text-sm text-muted-foreground">Shipped</span>
          </div>
          <div className="flex items-center gap-2">
            <Clock className="h-4 w-4 text-amber-500" />
            <span className="text-sm text-muted-foreground">In progress</span>
          </div>
          <div className="flex items-center gap-2">
            <Circle className="h-4 w-4 text-muted-foreground" />
            <span className="text-sm text-muted-foreground">Planned</span>
          </div>
          <div className="flex items-center gap-2">
            <Circle className="h-4 w-4 text-muted-foreground" />
            <span className="text-sm text-muted-foreground">Exploring</span>
          </div>
        </div>
      </MarketingRails>

      <DivideX />

      <MarketingRails>
        <GravitreReveal>
          <div className="mb-8">
            <h2 className="text-2xl font-semibold text-foreground mb-2">Shipped</h2>
            <p className="text-muted-foreground">Available now for all customers</p>
          </div>
        </GravitreReveal>
        <div className="grid gap-4 sm:grid-cols-2">
          {roadmapItems.shipped.map((item, i) => (
            <GravitreResolve key={item.title} delay={i * 0.04}>
              <div className="rounded-xl border border-border bg-gray-50 p-5 h-full">
                <div className="flex items-start justify-between gap-4 mb-2">
                  <h3 className="font-medium text-foreground">{item.title}</h3>
                  <StatusBadge status="shipped" />
                </div>
                <p className="text-sm text-muted-foreground">{item.description}</p>
              </div>
            </GravitreResolve>
          ))}
        </div>
      </MarketingRails>

      <DivideX />

      <MarketingRails>
        <GravitreReveal>
          <div className="mb-8">
            <h2 className="text-2xl font-semibold text-foreground mb-2">In progress</h2>
            <p className="text-muted-foreground">Actively being built</p>
          </div>
        </GravitreReveal>
        <div className="grid gap-4 sm:grid-cols-2">
          {roadmapItems.inProgress.map((item, i) => (
            <GravitreFlow key={item.title} delay={i * 0.04}>
              <div className="rounded-xl border border-border bg-gray-50 p-5 h-full">
                <div className="flex items-start justify-between gap-4 mb-2">
                  <h3 className="font-medium text-foreground">{item.title}</h3>
                  <StatusBadge status="inProgress" />
                </div>
                <p className="text-sm text-muted-foreground">{item.description}</p>
              </div>
            </GravitreFlow>
          ))}
        </div>
      </MarketingRails>

      <DivideX />

      <MarketingRails>
        <GravitreReveal>
          <div className="mb-8">
            <h2 className="text-2xl font-semibold text-foreground mb-2">Planned</h2>
            <p className="text-muted-foreground">On the roadmap</p>
          </div>
        </GravitreReveal>
        <div className="grid gap-4 sm:grid-cols-2">
          {roadmapItems.planned.map((item, i) => (
            <GravitreFlow key={item.title} delay={i * 0.04}>
              <div className="rounded-xl border border-border bg-gray-50 p-5 h-full">
                <div className="flex items-start justify-between gap-4 mb-2">
                  <h3 className="font-medium text-foreground">{item.title}</h3>
                  <StatusBadge status="planned" />
                </div>
                <p className="text-sm text-muted-foreground">{item.description}</p>
              </div>
            </GravitreFlow>
          ))}
        </div>
      </MarketingRails>

      <DivideX />

      <MarketingRails>
        <GravitreReveal>
          <div className="mb-8">
            <h2 className="text-2xl font-semibold text-foreground mb-2">Exploring</h2>
            <p className="text-muted-foreground">Under consideration — not committed</p>
          </div>
        </GravitreReveal>
        <div className="grid gap-4 sm:grid-cols-2">
          {roadmapItems.exploring.map((item, i) => (
            <GravitreFlow key={item.title} delay={i * 0.04}>
              <div className="rounded-xl border border-border bg-gray-50 p-5 h-full">
                <div className="flex items-start justify-between gap-4 mb-2">
                  <h3 className="font-medium text-foreground">{item.title}</h3>
                  <StatusBadge status="exploring" />
                </div>
                <p className="text-sm text-muted-foreground">{item.description}</p>
              </div>
            </GravitreFlow>
          ))}
        </div>
      </MarketingRails>

      <DivideX />

      <MarketingRails>
        <div className="mx-auto max-w-2xl rounded-2xl border border-border bg-gray-50 px-6 py-10 text-center">
          <h2 className="text-xl font-semibold text-foreground">Have a feature idea?</h2>
          <p className="mt-2 text-sm text-muted-foreground">
            Tell us what would help your team — email product or use Contact. No public vote board.
          </p>
          <div className="mt-6 flex flex-wrap items-center justify-center gap-3">
            <a
              href="mailto:product@gravitre.app?subject=Gravitre%20feature%20suggestion"
              className="inline-flex items-center gap-2 rounded-full bg-foreground px-5 py-2.5 text-sm font-medium text-white hover:bg-foreground/90"
            >
              Email product@gravitre.app
            </a>
            <Link
              href="/contact"
              className="inline-flex items-center gap-2 rounded-full border border-border px-5 py-2.5 text-sm font-medium text-foreground hover:bg-muted/50"
            >
              Contact
            </Link>
          </div>
        </div>
      </MarketingRails>

      <MarketingPageEndCta />
    </div>
  )
}
