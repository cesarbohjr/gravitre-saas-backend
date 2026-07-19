"use client"

import { useState } from "react"
import Link from "next/link"
import { motion, AnimatePresence } from "framer-motion"
import {
  ArrowRight,
  Headphones,
  TrendingUp,
  MessageSquare,
  Megaphone,
  Bot,
  Workflow,
  BookOpen,
  ShieldCheck,
  FileSpreadsheet,
  Search,
  PlugZap,
  Download,
  CheckCircle2,
} from "lucide-react"

const WHY_STATS = [
  { value: "60+", label: "Installable templates" },
  { value: "6", label: "Department packs" },
  { value: "Minutes", label: "Time to first run" },
]

const WHY_GUARANTEES = [
  "Readiness check before install",
  "Human approval on writes",
  "Version history and rollback",
]

type Category = "All" | "Agents" | "Workflows" | "Department packs" | "Knowledge"

const CATEGORIES: Category[] = ["All", "Agents", "Workflows", "Department packs", "Knowledge"]

type Asset = {
  name: string
  category: Exclude<Category, "All">
  subtitle: string
  description: string
  price: string
  icon: typeof Bot
  tone: string
}

const ASSETS: Asset[] = [
  {
    name: "Customer Success Pack",
    category: "Department packs",
    subtitle: "3 workflows · CS agent",
    description: "Health monitoring, QBR prep, and account-risk workflows bundled for CSM teams.",
    price: "Free",
    icon: Headphones,
    tone: "text-emerald-600 bg-emerald-100",
  },
  {
    name: "Revenue Operations Pack",
    category: "Department packs",
    subtitle: "RevOps + Sales agents",
    description: "Pipeline review, executive summaries, and CRM-connected RevOps rituals.",
    price: "Free",
    icon: TrendingUp,
    tone: "text-blue-600 bg-blue-100",
  },
  {
    name: "Support Operations Pack",
    category: "Department packs",
    subtitle: "Zendesk triage agent",
    description: "Ticket triage, support knowledge, and an optional SLA escalation workflow.",
    price: "$49",
    icon: MessageSquare,
    tone: "text-violet-600 bg-violet-100",
  },
  {
    name: "Marketing Operations Pack",
    category: "Department packs",
    subtitle: "Campaign production",
    description: "Multi-agent marketing production, attribution analysis, and campaign digests.",
    price: "Free",
    icon: Megaphone,
    tone: "text-amber-600 bg-amber-100",
  },
  {
    name: "Ticket Triage Agent",
    category: "Agents",
    subtitle: "Support operations",
    description: "Categorize and route inbound tickets, then hand off to humans with full context.",
    price: "Free",
    icon: Bot,
    tone: "text-emerald-600 bg-emerald-100",
  },
  {
    name: "RevOps Copilot",
    category: "Agents",
    subtitle: "Sales operations",
    description: "Enrich records, summarize pipeline, and draft follow-ups from connected CRM data.",
    price: "$29",
    icon: Bot,
    tone: "text-blue-600 bg-blue-100",
  },
  {
    name: "Deal Desk Workflow",
    category: "Workflows",
    subtitle: "Approval-gated",
    description: "Route quotes and discounts through the right approvers with a full audit trail.",
    price: "Free",
    icon: Workflow,
    tone: "text-emerald-600 bg-emerald-100",
  },
  {
    name: "Invoice Processing",
    category: "Workflows",
    subtitle: "Finance operations",
    description: "Parse invoices, match POs, and queue exceptions for human review before writes.",
    price: "Free",
    icon: FileSpreadsheet,
    tone: "text-amber-600 bg-amber-100",
  },
  {
    name: "Security Knowledge Base",
    category: "Knowledge",
    subtitle: "RAG source",
    description: "Curated threat-intel and policy docs, ready for agents with routing traces.",
    price: "Free",
    icon: ShieldCheck,
    tone: "text-rose-600 bg-rose-100",
  },
  {
    name: "Onboarding Playbook",
    category: "Knowledge",
    subtitle: "HR operations",
    description: "Structured onboarding checklists and request routing for new hires.",
    price: "Free",
    icon: BookOpen,
    tone: "text-teal-600 bg-teal-100",
  },
]

const STEPS = [
  { n: 1, icon: Search, title: "Browse", detail: "Filter by department or type" },
  { n: 2, icon: PlugZap, title: "Connect", detail: "Readiness check runs first" },
  { n: 3, icon: Download, title: "Install", detail: "Deploy in minutes" },
] as const

function CatalogCard({ asset, index }: { asset: Asset; index: number }) {
  const Icon = asset.icon
  const isPaid = asset.price !== "Free"
  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -8 }}
      transition={{ duration: 0.3, delay: Math.min(index * 0.04, 0.24) }}
      className="flex flex-col rounded-2xl border border-zinc-200 bg-white p-6 shadow-sm transition-all hover:-translate-y-1 hover:border-emerald-200 hover:shadow-md"
    >
      <div className={`flex h-12 w-12 items-center justify-center rounded-xl ${asset.tone}`}>
        <Icon className="h-6 w-6" />
      </div>
      <h3 className="mt-4 text-lg font-semibold text-zinc-900">{asset.name}</h3>
      <p className="mt-0.5 text-sm text-zinc-400">{asset.subtitle}</p>
      <p className="mt-3 flex-1 text-sm leading-relaxed text-zinc-600">{asset.description}</p>
      <div className="mt-6 flex items-center justify-between">
        <span
          className={`text-sm font-semibold ${isPaid ? "text-zinc-500" : "text-emerald-700"}`}
        >
          {asset.price}
        </span>
        <Link
          href="/get-started"
          className="inline-flex items-center gap-1.5 rounded-lg bg-emerald-600 px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-emerald-500"
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
    <div className="bg-white">
      {/* Hero + catalog */}
      <section className="relative overflow-hidden pt-28 pb-16 sm:pt-32">
        <div className="absolute inset-0 bg-gradient-to-b from-emerald-50 via-white to-white" />
        <div className="absolute -top-20 right-10 h-64 w-64 rounded-full bg-teal-200/30 blur-3xl" />

        <div className="relative mx-auto max-w-7xl px-6">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6 }}
            className="mx-auto max-w-3xl text-center"
          >
            <div className="mb-5 inline-flex items-center gap-2 rounded-full border border-emerald-200 bg-emerald-50 px-4 py-2">
              <span className="h-2 w-2 rounded-full bg-emerald-500" />
              <span className="text-sm font-medium text-emerald-700">Gravitre Marketplace</span>
            </div>
            <h1 className="text-4xl font-bold tracking-tight text-zinc-900 sm:text-5xl lg:text-6xl text-balance">
              60+ templates &{" "}
              <span className="bg-gradient-to-r from-emerald-600 to-teal-500 bg-clip-text text-transparent">
                department packs
              </span>
            </h1>
            <p className="mt-5 text-lg text-zinc-600 text-pretty">
              Workflows, agents, and knowledge — installable in minutes, not weeks.
            </p>
          </motion.div>

          {/* Filter pills */}
          <div className="mt-10 flex flex-wrap justify-center gap-3">
            {CATEGORIES.map((cat) => (
              <button
                key={cat}
                onClick={() => setActive(cat)}
                className={`rounded-full border px-5 py-2.5 text-sm font-medium transition-all ${
                  active === cat
                    ? "border-zinc-900 bg-zinc-900 text-white"
                    : "border-zinc-200 bg-white text-zinc-700 hover:border-zinc-300 hover:bg-zinc-50"
                }`}
              >
                {cat}
              </button>
            ))}
          </div>

          {/* Catalog grid */}
          <motion.div layout className="mt-10 grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
            <AnimatePresence mode="popLayout">
              {filtered.map((asset, i) => (
                <CatalogCard key={asset.name} asset={asset} index={i} />
              ))}
            </AnimatePresence>
          </motion.div>

          {/* Install steps */}
          <div className="mt-10 flex flex-wrap justify-center gap-4">
            {STEPS.map((step) => {
              const Icon = step.icon
              return (
                <div
                  key={step.n}
                  className="flex min-w-[220px] flex-1 items-center gap-3 rounded-xl border border-zinc-200 bg-white px-5 py-4 shadow-sm sm:max-w-xs"
                >
                  <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-emerald-100 text-sm font-bold text-emerald-700">
                    {step.n}
                  </div>
                  <div className="flex items-center gap-2">
                    <Icon className="h-4 w-4 text-emerald-600" />
                    <div>
                      <div className="text-sm font-semibold text-zinc-900">{step.title}</div>
                      <div className="text-xs text-zinc-500">{step.detail}</div>
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      </section>

      {/* Why the marketplace — compact stats + governance guarantees (no
         duplicate headline/pack cards; the catalog above already covers them) */}
      <section className="border-t border-zinc-200 bg-zinc-50 py-20 lg:py-24">
        <div className="mx-auto max-w-6xl px-6">
          <div className="grid gap-4 sm:grid-cols-3">
            {WHY_STATS.map((stat, i) => (
              <motion.div
                key={stat.label}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: i * 0.08 }}
                className="rounded-2xl border border-zinc-200 bg-white p-6 text-center shadow-sm"
              >
                <div className="text-3xl font-bold text-zinc-900">{stat.value}</div>
                <div className="mt-1 text-sm text-zinc-500">{stat.label}</div>
              </motion.div>
            ))}
          </div>
          <ul className="mx-auto mt-10 grid max-w-3xl gap-3 sm:grid-cols-3">
            {WHY_GUARANTEES.map((item) => (
              <li
                key={item}
                className="flex items-center gap-2 rounded-xl border border-zinc-200 bg-white px-4 py-3 text-sm text-zinc-700"
              >
                <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-600" />
                {item}
              </li>
            ))}
          </ul>
        </div>
      </section>

      {/* CTA */}
      <section className="relative overflow-hidden border-t border-zinc-200 bg-gradient-to-b from-white to-emerald-50 py-24">
        <div className="mx-auto max-w-3xl px-6 text-center">
          <h2 className="text-3xl font-bold tracking-tight text-zinc-900 sm:text-4xl text-balance">
            Start from a proven template
          </h2>
          <p className="mt-4 text-lg text-zinc-600 text-pretty">
            Every install runs a readiness check first and keeps the same approval gates as the rest of Gravitre.
          </p>
          <ul className="mx-auto mt-8 flex max-w-2xl flex-col gap-3 text-left sm:flex-row sm:justify-center sm:gap-8">
            {["Readiness check before install", "Human approval on writes", "Version history and rollback"].map(
              (item) => (
                <li key={item} className="flex items-center gap-2 text-sm text-zinc-700">
                  <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-600" />
                  {item}
                </li>
              ),
            )}
          </ul>
          <div className="mt-9 flex flex-wrap justify-center gap-4">
            <Link
              href="/get-started"
              className="inline-flex items-center gap-2 rounded-full bg-emerald-600 px-7 py-3.5 text-sm font-semibold text-white transition-colors hover:bg-emerald-500"
            >
              Browse the marketplace
              <ArrowRight className="h-4 w-4" />
            </Link>
            <Link
              href="/features/technology"
              className="inline-flex items-center gap-2 rounded-full border border-zinc-300 bg-white px-7 py-3.5 text-sm font-semibold text-zinc-900 transition-colors hover:bg-zinc-50"
            >
              See the technology
            </Link>
          </div>
        </div>
      </section>
    </div>
  )
}
