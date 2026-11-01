"use client"

import { useState, type ComponentType } from "react"
import Link from "next/link"
import Image from "next/image"
import { motion, AnimatePresence } from "framer-motion"
import {
  Headphones,
  TrendingUp,
  Megaphone,
  Download,
  CheckCircle2,
} from "lucide-react"
import {
  NucleoAgent,
  NucleoConnector,
  NucleoSearch,
  NucleoWorkflow,
} from "@/components/icons/nucleo/semantic"
import { MARKETING_COPY } from "@/lib/marketing-copy"
import { marketArtFor, type MarketArtName } from "@/lib/marketplace-category-art"
import { DivideX } from "@/components/marketing/nodus/divide"
import { MarketingScene } from "@/components/marketing/nodus/scene"
import {
  MarketingPageEndCta,
  MarketingPageHero,
  MarketingRails,
} from "@/components/marketing/nodus/page-shell"
import {
  GravitreReveal,
  GravitreSection,
  GravitreSectionHeader,
  GravitreTrace,
  MARKETPLACE_TRACE_STAGES,
  StageTraceVisual,
} from "@/components/marketing/system"

const WHY_STATS = [
  { value: "Templates", label: "Installable for your stack" },
  { value: "Department packs", label: "Bundled by team" },
  { value: "Same gates", label: "As chat & workflows" },
]

const WHY_GUARANTEES = [
  "Readiness check before install",
  "Human approval on writes",
  "Version history and rollback",
]

type Category = "All" | "Agents" | "Workflows" | "Department packs"

const CATEGORIES: Category[] = ["All", "Agents", "Workflows", "Department packs"]

type AssetIcon = ComponentType<{ className?: string }>

type Asset = {
  name: string
  category: Exclude<Category, "All">
  subtitle: string
  description: string
  availability: "Included"
  icon: AssetIcon
  tone: string
  /** Cover from the app's Marketplace card library, one per card. */
  art: MarketArtName
}

const ASSETS: Asset[] = [
  {
    name: "Customer Success Pack",
    art: "market-new-customers",
    category: "Department packs",
    subtitle: "3 workflows · CS agent",
    description: "Health monitoring, QBR prep, and account-risk workflows bundled for CSM teams.",
    availability: "Included",
    icon: Headphones,
    tone: "text-primary bg-primary/15",
  },
  {
    name: "Revenue Operations Pack",
    art: "market-revenue",
    category: "Department packs",
    subtitle: "RevOps + Sales agents",
    description: "Pipeline review, executive summaries, and CRM-connected RevOps rituals.",
    availability: "Included",
    icon: TrendingUp,
    tone: "text-info bg-info/15",
  },
  {
    name: "Support Operations Pack",
    art: "market-tickets",
    category: "Department packs",
    subtitle: "Zendesk triage agent",
    description: "Ticket triage, support knowledge, and an optional SLA escalation workflow.",
    availability: "Included",
    icon: NucleoAgent,
    tone: "text-[color:var(--g-electric)] bg-[color:var(--g-emerald-pale)]",
  },
  {
    name: "Marketing Operations Pack",
    art: "market-campaigns",
    category: "Department packs",
    subtitle: "Campaign production",
    description: "Multi-agent marketing production, attribution analysis, and campaign digests.",
    availability: "Included",
    icon: Megaphone,
    tone: "text-warning-text bg-warning/15",
  },
  {
    name: "Ticket Triage Agent",
    art: "market-support",
    category: "Agents",
    subtitle: "Support operations",
    description: "Categorize and route inbound tickets, then hand off to humans with full context.",
    availability: "Included",
    icon: NucleoAgent,
    tone: "text-primary bg-primary/15",
  },
  {
    name: "RevOps Copilot",
    art: "market-pipeline",
    category: "Agents",
    subtitle: "Sales operations",
    description: "Enrich records, summarize pipeline, and draft follow-ups from connected CRM data.",
    availability: "Included",
    icon: NucleoAgent,
    tone: "text-info bg-info/15",
  },
  {
    name: "Lead Enrichment Agent",
    art: "market-leads",
    category: "Agents",
    subtitle: "Marketing operations",
    description: "Enrich inbound leads from connected tools and route them to the right owner for review.",
    availability: "Included",
    icon: NucleoAgent,
    tone: "text-brand-text bg-brand/15",
  },
  {
    name: "Deal Desk Workflow",
    art: "market-deals",
    category: "Workflows",
    subtitle: "Approval-gated",
    description: "Route quotes and discounts through the right approvers with a full audit trail.",
    availability: "Included",
    icon: NucleoWorkflow,
    tone: "text-primary bg-primary/15",
  },
]

const STEPS = [
  { n: 1, icon: NucleoSearch, title: "Browse", detail: "Filter by department or type" },
  { n: 2, icon: NucleoConnector, title: "Connect", detail: "Readiness check runs first" },
  { n: 3, icon: Download, title: "Install", detail: "Deploy in minutes" },
] as const

function CatalogCard({ asset, index }: { asset: Asset; index: number }) {
  const Icon = asset.icon
  const art = marketArtFor(asset.art)
  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -8 }}
      transition={{ duration: 0.3, delay: Math.min(index * 0.04, 0.24) }}
      className="group flex flex-col overflow-hidden rounded-2xl border border-divide bg-[color:var(--g-marketing-surface)] shadow-sm transition-all hover:-translate-y-1 hover:border-primary/20 hover:bg-card hover:shadow-md"
    >
      <div className="relative aspect-[16/9] overflow-hidden bg-[#E7ECE3]">
        <Image
          src={art.src}
          alt={art.alt}
          fill
          unoptimized
          sizes="(min-width: 1024px) 25vw, (min-width: 640px) 50vw, 100vw"
          className="object-cover transition-transform duration-500 group-hover:scale-[1.04]"
        />
        <span className="absolute left-3 top-3 inline-flex items-center gap-1.5 rounded-full bg-white/90 px-2.5 py-1 text-[11px] font-medium text-charcoal-700 shadow-sm">
          <span className="size-1.5 rounded-full bg-brand" />
          {art.label}
        </span>
      </div>
      <div className="flex flex-1 flex-col p-6 pt-5">
        <div className={`flex h-10 w-10 items-center justify-center rounded-xl ${asset.tone}`}>
          <Icon className="h-5 w-5" />
        </div>
        <h3 className="mt-4 text-lg font-semibold text-foreground">{asset.name}</h3>
        <p className="mt-0.5 text-sm text-muted-foreground">{asset.subtitle}</p>
        <p className="mt-3 flex-1 text-sm leading-relaxed text-muted-foreground">{asset.description}</p>
        <div className="mt-6 flex items-center justify-between">
          <span className="text-sm font-semibold text-primary">{asset.availability}</span>
          <Link
            href="/get-started"
            className="inline-flex items-center gap-1.5 rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground transition-colors hover:bg-primary/100"
          >
            Install
          </Link>
        </div>
      </div>
    </motion.div>
  )
}

export function MarketplacePage() {
  const [active, setActive] = useState<Category>("All")
  const filtered = active === "All" ? ASSETS : ASSETS.filter((a) => a.category === active)

  return (
    <div className="bg-[color:var(--g-marketing-canvas)]">
      <MarketingPageHero
        badge="Gravitre Marketplace"
        title={
          <>
            {MARKETING_COPY.marketplace.title.split(" for the same brain")[0]} for the{" "}
            <span className="text-brand">same brain</span>
          </>
        }
        description={MARKETING_COPY.marketplace.subtitle}
      >
        <div className="mt-8 flex flex-wrap justify-center gap-3">
          {CATEGORIES.map((cat) => (
            <button
              key={cat}
              type="button"
              onClick={() => setActive(cat)}
              className={`rounded-full border px-5 py-2 text-sm font-medium transition-all ${
                active === cat
                  ? "border-charcoal-900 bg-charcoal-900 text-background"
                  : "border-divide bg-card text-gray-600 hover:text-charcoal-700"
              }`}
            >
              {cat}
            </button>
          ))}
        </div>
      </MarketingPageHero>

      <DivideX />

      <GravitreSection>
        <GravitreSectionHeader
          align="center"
          badge="Marketplace path"
          title="From browse to live under the same gates"
          description="One signature TRACE — pick a template, pass readiness, clear the approval gate, then run live."
          className="mb-6"
        />
        <GravitreTrace>
          <StageTraceVisual
            stages={MARKETPLACE_TRACE_STAGES}
            gradientId="marketplace-trace"
            payloads={["Deal Desk Workflow", "RevOps Copilot", "Lead Enrichment Agent", "Ticket Triage Agent"]}
            ariaLabel="Marketplace path from browse through readiness and approval gate to live"
            caption="Browse → readiness → approval gate → live — same governance as chat and workflows."
          />
        </GravitreTrace>
      </GravitreSection>

      <DivideX />

      <MarketingRails>
          <motion.div layout className="grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
            <AnimatePresence mode="popLayout">
              {filtered.map((asset, i) => (
                <CatalogCard key={asset.name} asset={asset} index={i} />
              ))}
            </AnimatePresence>
          </motion.div>

          <div className="mt-10 grid gap-4 sm:grid-cols-3">
            {STEPS.map((step) => {
              const Icon = step.icon
              return (
                <div
                  key={step.n}
                  className="border-divide flex items-center gap-3 rounded-lg border bg-[color:var(--g-marketing-surface)] px-5 py-4"
                >
                  <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-[color:var(--brand-soft)] text-sm font-bold text-[color:var(--brand)]">
                    {step.n}
                  </div>
                  <div className="flex items-center gap-2">
                    <Icon className="h-4 w-4 text-[color:var(--brand)]" />
                    <div>
                      <div className="text-sm font-semibold text-foreground">{step.title}</div>
                      <div className="text-xs text-muted-foreground">{step.detail}</div>
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
      </MarketingRails>

      <DivideX />

      <MarketingRails>
          <MarketingScene
            name="marketing/marketplace"
            alt="A shelf of agent and workflow templates, one being installed"
            width={400}
            height={300}
            className="mx-auto mb-10 max-w-xl"
          />
          <div className="grid gap-4 sm:grid-cols-3">
            {WHY_STATS.map((stat, i) => (
              <GravitreReveal
                key={stat.label}
                delay={i * 0.08}
                className="border-divide rounded-lg border bg-[color:var(--g-marketing-surface)] p-6 text-center"
              >
                <div className="text-3xl font-bold text-foreground">{stat.value}</div>
                <div className="mt-1 text-sm text-muted-foreground">{stat.label}</div>
              </GravitreReveal>
            ))}
          </div>
          <ul className="mt-4 grid gap-4 sm:grid-cols-3">
            {WHY_GUARANTEES.map((item) => (
              <li
                key={item}
                className="border-divide flex items-center gap-2 rounded-lg border bg-card px-4 py-3 text-sm text-foreground"
              >
                <CheckCircle2 className="h-4 w-4 shrink-0 text-[color:var(--brand)]" />
                {item}
              </li>
            ))}
          </ul>
      </MarketingRails>

      <MarketingPageEndCta />
    </div>
  )
}
