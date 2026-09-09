"use client"

import { useState, type ComponentType } from "react"
import Link from "next/link"
import { motion, AnimatePresence } from "framer-motion"
import {
  Headphones,
  TrendingUp,
  Megaphone,
  BookOpen,
  FileSpreadsheet,
  Download,
  CheckCircle2,
} from "lucide-react"
import {
  NucleoAgent,
  NucleoApproval,
  NucleoConnector,
  NucleoSearch,
  NucleoWorkflow,
} from "@/components/icons/nucleo/semantic"
import { MARKETING_COPY } from "@/lib/marketing-copy"
import { DivideX } from "@/components/marketing/nodus/divide"
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

type Category = "All" | "Agents" | "Workflows" | "Department packs" | "Knowledge"

const CATEGORIES: Category[] = ["All", "Agents", "Workflows", "Department packs", "Knowledge"]

type AssetIcon = ComponentType<{ className?: string }>

type Asset = {
  name: string
  category: Exclude<Category, "All">
  subtitle: string
  description: string
  availability: "Included"
  icon: AssetIcon
  tone: string
}

const ASSETS: Asset[] = [
  {
    name: "Customer Success Pack",
    category: "Department packs",
    subtitle: "3 workflows · CS agent",
    description: "Health monitoring, QBR prep, and account-risk workflows bundled for CSM teams.",
    availability: "Included",
    icon: Headphones,
    tone: "text-primary bg-primary/15",
  },
  {
    name: "Revenue Operations Pack",
    category: "Department packs",
    subtitle: "RevOps + Sales agents",
    description: "Pipeline review, executive summaries, and CRM-connected RevOps rituals.",
    availability: "Included",
    icon: TrendingUp,
    tone: "text-blue-600 bg-blue-100",
  },
  {
    name: "Support Operations Pack",
    category: "Department packs",
    subtitle: "Zendesk triage agent",
    description: "Ticket triage, support knowledge, and an optional SLA escalation workflow.",
    availability: "Included",
    icon: NucleoAgent,
    tone: "text-violet-600 bg-violet-100",
  },
  {
    name: "Marketing Operations Pack",
    category: "Department packs",
    subtitle: "Campaign production",
    description: "Multi-agent marketing production, attribution analysis, and campaign digests.",
    availability: "Included",
    icon: Megaphone,
    tone: "text-amber-600 bg-amber-100",
  },
  {
    name: "Ticket Triage Agent",
    category: "Agents",
    subtitle: "Support operations",
    description: "Categorize and route inbound tickets, then hand off to humans with full context.",
    availability: "Included",
    icon: NucleoAgent,
    tone: "text-primary bg-primary/15",
  },
  {
    name: "RevOps Copilot",
    category: "Agents",
    subtitle: "Sales operations",
    description: "Enrich records, summarize pipeline, and draft follow-ups from connected CRM data.",
    availability: "Included",
    icon: NucleoAgent,
    tone: "text-blue-600 bg-blue-100",
  },
  {
    name: "Deal Desk Workflow",
    category: "Workflows",
    subtitle: "Approval-gated",
    description: "Route quotes and discounts through the right approvers with a full audit trail.",
    availability: "Included",
    icon: NucleoWorkflow,
    tone: "text-primary bg-primary/15",
  },
  {
    name: "Invoice Processing",
    category: "Workflows",
    subtitle: "Finance operations",
    description: "Parse invoices, match POs, and queue exceptions for human review before writes.",
    availability: "Included",
    icon: FileSpreadsheet,
    tone: "text-amber-600 bg-amber-100",
  },
  {
    name: "Security Knowledge Base",
    category: "Knowledge",
    subtitle: "RAG source",
    description: "Curated threat-intel and policy docs, ready for agents with routing traces.",
    availability: "Included",
    icon: NucleoApproval,
    tone: "text-rose-600 bg-rose-100",
  },
  {
    name: "Onboarding Playbook",
    category: "Knowledge",
    subtitle: "HR operations",
    description: "Structured onboarding checklists and request routing for new hires.",
    availability: "Included",
    icon: BookOpen,
    tone: "text-teal-600 bg-teal-100",
  },
]

const STEPS = [
  { n: 1, icon: NucleoSearch, title: "Browse", detail: "Filter by department or type" },
  { n: 2, icon: NucleoConnector, title: "Connect", detail: "Readiness check runs first" },
  { n: 3, icon: Download, title: "Install", detail: "Deploy in minutes" },
] as const

function CatalogCard({ asset, index }: { asset: Asset; index: number }) {
  const Icon = asset.icon
  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -8 }}
      transition={{ duration: 0.3, delay: Math.min(index * 0.04, 0.24) }}
      className="flex flex-col rounded-2xl border border-divide bg-gray-50 p-6 shadow-sm transition-all hover:-translate-y-1 hover:border-primary/20 hover:bg-white hover:shadow-md"
    >
      <div className={`flex h-12 w-12 items-center justify-center rounded-xl ${asset.tone}`}>
        <Icon className="h-6 w-6" />
      </div>
      <h3 className="mt-4 text-lg font-semibold text-foreground">{asset.name}</h3>
      <p className="mt-0.5 text-sm text-muted-foreground">{asset.subtitle}</p>
      <p className="mt-3 flex-1 text-sm leading-relaxed text-muted-foreground">{asset.description}</p>
      <div className="mt-6 flex items-center justify-between">
        <span className="text-sm font-semibold text-primary">{asset.availability}</span>
        <Link
          href="/get-started"
          className="inline-flex items-center gap-1.5 rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-primary/100"
        >
          Install
        </Link>
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
                  ? "border-charcoal-900 bg-charcoal-900 text-white"
                  : "border-divide bg-white text-gray-600 hover:text-charcoal-700"
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

          <div className="mt-10 flex flex-wrap justify-center gap-4">
            {STEPS.map((step) => {
              const Icon = step.icon
              return (
                <div
                  key={step.n}
                  className="border-divide flex min-w-[220px] flex-1 items-center gap-3 rounded-lg border bg-gray-50 px-5 py-4 sm:max-w-xs"
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
          <div className="grid gap-4 sm:grid-cols-3">
            {WHY_STATS.map((stat, i) => (
              <GravitreReveal
                key={stat.label}
                delay={i * 0.08}
                className="border-divide rounded-lg border bg-gray-50 p-6 text-center"
              >
                <div className="text-3xl font-bold text-foreground">{stat.value}</div>
                <div className="mt-1 text-sm text-muted-foreground">{stat.label}</div>
              </GravitreReveal>
            ))}
          </div>
          <ul className="mx-auto mt-10 grid max-w-3xl gap-3 sm:grid-cols-3">
            {WHY_GUARANTEES.map((item) => (
              <li
                key={item}
                className="border-divide flex items-center gap-2 rounded-lg border bg-white px-4 py-3 text-sm text-foreground"
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
