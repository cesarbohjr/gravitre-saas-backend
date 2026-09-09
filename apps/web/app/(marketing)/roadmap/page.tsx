"use client"

import Link from "next/link"
import { useRef } from "react"
import {
  motion,
  useReducedMotion,
  useScroll,
  useTransform,
  type MotionValue,
} from "framer-motion"
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

const NARRATIVE_STAGES = [
  {
    id: "connect",
    label: "Connect",
    blurb: "Link the tools and data your team already uses — governed connectors, not one-off scripts.",
  },
  {
    id: "understand",
    label: "Understand",
    blurb: "Gravitre reads context across systems so agents know what matters before they act.",
  },
  {
    id: "coordinate",
    label: "Coordinate",
    blurb: "Agents and workflows share governed context — coordinated work, not orphan automations.",
  },
  {
    id: "act",
    label: "Act",
    blurb: "Writes and external actions pass through approval gates you control.",
  },
  {
    id: "verify",
    label: "Verify",
    blurb: "Outcomes, audit trails, and operator review close the loop on every run.",
  },
  {
    id: "learn",
    label: "Learn",
    blurb: "GIBE learns from approved outcomes — org memory that compounds over time.",
  },
] as const

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

function NarrativeStagePanel({
  index,
  progress,
}: {
  index: number
  progress: MotionValue<number>
}) {
  const stage = NARRATIVE_STAGES[index]
  const n = NARRATIVE_STAGES.length
  const segment = 1 / n
  const center = (index + 0.5) * segment
  const opacity = useTransform(
    progress,
    [center - segment * 0.55, center, center + segment * 0.55],
    [0, 1, 0],
  )
  const y = useTransform(
    progress,
    [center - segment * 0.55, center, center + segment * 0.55],
    [12, 0, -12],
  )

  return (
    <motion.div style={{ opacity, y }} className="absolute inset-0 flex flex-col justify-center">
      <p className="text-sm font-medium uppercase tracking-wide text-brand">{stage.label}</p>
      <p className="mt-3 max-w-lg text-2xl font-semibold text-foreground md:text-3xl">{stage.blurb}</p>
    </motion.div>
  )
}

function RoadmapStickyNarrative() {
  const ref = useRef<HTMLDivElement>(null)
  const reduce = useReducedMotion()
  const { scrollYProgress } = useScroll({
    target: ref,
    offset: ["start start", "end end"],
  })

  const activeIndex = useTransform(scrollYProgress, (p) =>
    Math.min(Math.floor(p * NARRATIVE_STAGES.length), NARRATIVE_STAGES.length - 1),
  )

  if (reduce) {
    return (
      <GravitreSection>
        <GravitreSectionHeader
          badge="Product spine"
          title="Connect → Learn"
          description="How Gravitre moves from connected systems to governed outcomes and org learning."
        />
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {NARRATIVE_STAGES.map((stage) => (
            <div key={stage.id} className="rounded-xl border border-divide bg-gray-50 p-5">
              <p className="text-sm font-medium text-brand">{stage.label}</p>
              <p className="mt-2 text-sm text-muted-foreground">{stage.blurb}</p>
            </div>
          ))}
        </div>
      </GravitreSection>
    )
  }

  return (
    <div ref={ref} className="relative" style={{ height: `${NARRATIVE_STAGES.length * 70}vh` }}>
      <div className="sticky top-16 flex min-h-[70vh] items-center py-12 md:top-20">
        <div className="mx-auto grid w-full max-w-5xl gap-10 px-4 md:grid-cols-[minmax(0,1fr)_minmax(0,1.2fr)] md:px-8">
          <div className="flex flex-col justify-center gap-2">
            {NARRATIVE_STAGES.map((stage, i) => (
              <StagePill key={stage.id} index={i} activeIndex={activeIndex} label={stage.label} />
            ))}
          </div>
          <div className="relative min-h-[200px]">
            {NARRATIVE_STAGES.map((_, i) => (
              <NarrativeStagePanel key={NARRATIVE_STAGES[i].id} index={i} progress={scrollYProgress} />
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}

function StagePill({
  index,
  activeIndex,
  label,
}: {
  index: number
  activeIndex: MotionValue<number>
  label: string
}) {
  const opacity = useTransform(activeIndex, (v) => (v === index ? 1 : 0.45))
  const scale = useTransform(activeIndex, (v) => (v === index ? 1 : 0.98))

  return (
    <motion.div
      style={{ opacity, scale }}
      className="flex items-center gap-3 rounded-lg border border-divide bg-white px-4 py-2.5"
    >
      <span
        className={`h-2 w-2 shrink-0 rounded-full ${index === NARRATIVE_STAGES.length - 1 ? "bg-primary" : "bg-[color:var(--g-intelligence)]"}`}
      />
      <span className="text-sm font-medium text-foreground">{label}</span>
    </motion.div>
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
            caption="Connect → Learn — framer-motion sticky narrative below; no GSAP."
          />
        </GravitreTrace>
      </GravitreSection>

      <DivideX />

      <RoadmapStickyNarrative />

      <DivideX />

      <MarketingRails className="py-8">
        <div className="flex flex-wrap items-center justify-center gap-4">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="h-4 w-4 text-primary" />
            <span className="text-sm text-muted-foreground">Shipped</span>
          </div>
          <div className="flex items-center gap-2">
            <Clock className="h-4 w-4 text-amber-600" />
            <span className="text-sm text-muted-foreground">In progress</span>
          </div>
          <div className="flex items-center gap-2">
            <Circle className="h-4 w-4 text-charcoal" />
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
        <div className="mx-auto max-w-4xl">
          <GravitreReveal className="flex items-center gap-3 mb-8">
            <Clock className="h-5 w-5 text-amber-600" />
            <h2 className="text-xl font-semibold text-foreground">In progress</h2>
          </GravitreReveal>
          <div className="space-y-4">
            {roadmapItems.inProgress.map((item, i) => (
              <GravitreFlow
                key={item.title}
                delay={i * 0.05}
                className="rounded-xl border border-border bg-card p-5 shadow-sm"
              >
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1">
                    <div className="flex items-center gap-3 mb-2">
                      <h3 className="font-medium text-foreground">{item.title}</h3>
                      <StatusBadge status="inProgress" />
                    </div>
                    <p className="text-sm text-muted-foreground">{item.description}</p>
                  </div>
                </div>
              </GravitreFlow>
            ))}
          </div>
        </div>
      </MarketingRails>

      <DivideX />

      <MarketingRails>
        <div className="mx-auto max-w-4xl">
          <GravitreReveal className="flex items-center gap-3 mb-8">
            <Circle className="h-5 w-5 text-charcoal" />
            <h2 className="text-xl font-semibold text-foreground">Planned</h2>
          </GravitreReveal>
          <div className="space-y-3">
            {roadmapItems.planned.map((item, i) => (
              <GravitreFlow
                key={item.title}
                delay={i * 0.05}
                className="rounded-xl border border-border bg-card p-4 shadow-sm"
              >
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <div className="flex items-center gap-3 mb-1">
                      <h3 className="font-medium text-foreground">{item.title}</h3>
                      <StatusBadge status="planned" />
                    </div>
                    <p className="text-sm text-muted-foreground mt-0.5">{item.description}</p>
                  </div>
                </div>
              </GravitreFlow>
            ))}
          </div>
        </div>
      </MarketingRails>

      <DivideX />

      <MarketingRails>
        <div className="mx-auto max-w-4xl">
          <GravitreReveal className="flex items-center gap-3 mb-8">
            <Circle className="h-5 w-5 text-muted-foreground" />
            <h2 className="text-xl font-semibold text-foreground">Exploring</h2>
            <span className="text-xs text-muted-foreground">Ideas we&apos;re considering</span>
          </GravitreReveal>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {roadmapItems.exploring.map((item, i) => (
              <GravitreFlow
                key={item.title}
                delay={i * 0.05}
                className="rounded-xl border border-border bg-card p-4 shadow-sm"
              >
                <div className="flex items-center gap-2 mb-1">
                  <h3 className="font-medium text-foreground text-sm">{item.title}</h3>
                  <StatusBadge status="exploring" />
                </div>
                <p className="text-xs text-muted-foreground mt-1 line-clamp-2">{item.description}</p>
              </GravitreFlow>
            ))}
          </div>
        </div>
      </MarketingRails>

      <DivideX />

      <MarketingRails>
        <div className="mx-auto max-w-4xl">
          <GravitreReveal className="flex items-center gap-3 mb-8">
            <CheckCircle2 className="h-5 w-5 text-primary" />
            <h2 className="text-xl font-semibold text-foreground">Recently shipped</h2>
          </GravitreReveal>
          <div className="grid gap-3 sm:grid-cols-2">
            {roadmapItems.shipped.map((item, i) => (
              <GravitreResolve
                key={item.title}
                delay={i * 0.05}
                className="rounded-xl border border-primary/20 bg-primary/10 p-4"
              >
                <div className="flex items-center gap-2 mb-1">
                  <CheckCircle2 className="h-4 w-4 text-primary" />
                  <h3 className="font-medium text-foreground text-sm">{item.title}</h3>
                  <StatusBadge status="shipped" />
                </div>
                <p className="text-xs text-muted-foreground ml-6">{item.description}</p>
              </GravitreResolve>
            ))}
          </div>
        </div>
      </MarketingRails>

      <DivideX />

      <MarketingRails>
        <div id="suggest" className="mx-auto max-w-xl text-center">
          <GravitreResolve>
            <h2 className="text-2xl font-semibold text-foreground mb-4">Have an idea?</h2>
            <p className="text-muted-foreground mb-8">
              Email product@gravitre.app or reach us through contact — we read every suggestion.
            </p>
            <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
              <a
                href="mailto:product@gravitre.app?subject=Gravitre%20feature%20suggestion"
                className="inline-flex items-center gap-2 rounded-full bg-foreground px-6 py-3 text-sm font-medium text-white transition-all hover:bg-foreground/90"
              >
                Email product@gravitre.app
                <ArrowRight className="h-4 w-4" />
              </a>
              <Link
                href="/contact"
                className="inline-flex items-center gap-2 rounded-full border border-border bg-card px-6 py-3 text-sm font-medium text-foreground transition-colors hover:bg-muted/50"
              >
                Contact form
              </Link>
            </div>
          </GravitreResolve>
        </div>
      </MarketingRails>

      <MarketingPageEndCta />
    </div>
  )
}
