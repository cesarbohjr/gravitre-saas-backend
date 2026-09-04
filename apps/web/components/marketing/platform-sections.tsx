"use client"

import Link from "next/link"
import { motion } from "framer-motion"
import {
  ArrowRight,
  BarChart3,
  Brain,
  CheckCircle2,
  Database,
  Package,
  Shield,
  Sparkles,
  Workflow,
} from "lucide-react"
import { MARKETING_COPY } from "@/lib/marketing-copy"

const flowIcons = [Database, Brain, Sparkles, CheckCircle2] as const

export function GibeDataFlowSection({ compact = false }: { compact?: boolean }) {
  const copy = MARKETING_COPY.gibeDataFlow

  return (
    <section className={`relative border-t border-border bg-muted/50 ${compact ? "py-16 lg:py-20" : "py-24 lg:py-28"}`}>
      <div className="mx-auto max-w-7xl px-6">
        <motion.div
          initial={{ opacity: 0, y: 24 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          className="mx-auto max-w-3xl text-center mb-12"
        >
          <div className="mb-4 inline-flex items-center gap-2 rounded-full border border-primary/20 bg-primary/10 px-4 py-2">
            <Brain className="h-4 w-4 text-primary" />
            <span className="text-sm font-medium text-primary">{copy.badge}</span>
          </div>
          <h2 className="text-3xl sm:text-4xl font-bold tracking-tight text-foreground text-balance">{copy.title}</h2>
          <p className="mt-4 text-lg text-muted-foreground text-pretty">{copy.subtitle}</p>
        </motion.div>

        <div className="relative">
          <div className="hidden lg:block absolute top-1/2 left-[12%] right-[12%] h-0.5 bg-gradient-to-r from-emerald-200 via-teal-200 to-emerald-200 -translate-y-1/2" />
          <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
            {copy.steps.map((step, i) => {
              const Icon = flowIcons[i] ?? Database
              return (
                <motion.div
                  key={step.title}
                  initial={{ opacity: 0, y: 16 }}
                  whileInView={{ opacity: 1, y: 0 }}
                  viewport={{ once: true }}
                  transition={{ delay: i * 0.08 }}
                  className="relative rounded-2xl border border-border bg-card p-6 shadow-sm"
                >
                  <div className="mb-4 flex items-center gap-3">
                    <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary/15">
                      <Icon className="h-5 w-5 text-primary" />
                    </div>
                    <span className="text-xs font-semibold uppercase tracking-wider text-primary">
                      {String(i + 1).padStart(2, "0")}
                    </span>
                  </div>
                  <h3 className="text-lg font-semibold text-foreground">{step.title}</h3>
                  <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{step.description}</p>
                </motion.div>
              )
            })}
          </div>
        </div>
      </div>
    </section>
  )
}

export function TransparencyMetricsSection() {
  const copy = MARKETING_COPY.transparencyMetrics
  const tierStyles = [
    "border-primary/20 bg-primary/10/50",
    "border-amber-200 bg-amber-50/50",
    "border-border bg-muted/50",
  ]

  return (
    <section className="relative py-24 lg:py-28 border-t border-border bg-card">
      <div className="mx-auto max-w-7xl px-6">
        <motion.div
          initial={{ opacity: 0, y: 24 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          className="mx-auto max-w-3xl text-center mb-12"
        >
          <div className="mb-4 inline-flex items-center gap-2 rounded-full border border-border bg-muted/50 px-4 py-2">
            <BarChart3 className="h-4 w-4 text-muted-foreground" />
            <span className="text-sm font-medium text-foreground">{copy.badge}</span>
          </div>
          <h2 className="text-3xl sm:text-4xl font-bold tracking-tight text-foreground">{copy.title}</h2>
          <p className="mt-4 text-lg text-muted-foreground">{copy.subtitle}</p>
        </motion.div>

        <div className="grid gap-6 lg:grid-cols-3">
          {copy.tiers.map((tier, i) => (
            <motion.div
              key={tier.title}
              initial={{ opacity: 0, y: 16 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: i * 0.08 }}
              className={`rounded-2xl border p-6 ${tierStyles[i] ?? tierStyles[0]}`}
            >
              <h3 className="text-lg font-semibold text-foreground">{tier.title}</h3>
              <p className="mt-2 text-sm leading-relaxed text-foreground">{tier.description}</p>
              <ul className="mt-4 space-y-2">
                {tier.examples.map((example) => (
                  <li key={example} className="flex gap-2 text-sm text-muted-foreground">
                    <span aria-hidden className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-zinc-400" />
                    {example}
                  </li>
                ))}
              </ul>
            </motion.div>
          ))}
        </div>

        <motion.div
          initial={{ opacity: 0, y: 12 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          className="mt-10 text-center"
        >
          <Link
            href={copy.blogLink.href}
            className="inline-flex items-center gap-2 text-sm font-medium text-primary hover:text-primary"
          >
            {copy.blogLink.label}
            <ArrowRight className="h-4 w-4" />
          </Link>
        </motion.div>
      </div>
    </section>
  )
}

export function MarketplaceHighlightsSection() {
  const copy = MARKETING_COPY.marketplace

  return (
    <section className="relative py-24 lg:py-28 border-t border-border bg-muted/50">
      <div className="mx-auto max-w-7xl px-6">
        <div className="grid gap-12 lg:grid-cols-2 lg:items-start">
          <motion.div
            initial={{ opacity: 0, y: 24 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
          >
            <div className="mb-4 inline-flex items-center gap-2 rounded-full border border-amber-200 bg-amber-50 px-4 py-2">
              <Package className="h-4 w-4 text-amber-700" />
              <span className="text-sm font-medium text-amber-800">{copy.badge}</span>
            </div>
            <h2 className="text-3xl sm:text-4xl font-bold tracking-tight text-foreground text-balance">{copy.title}</h2>
            <p className="mt-4 text-lg text-muted-foreground">{copy.subtitle}</p>

            <div className="mt-8 grid grid-cols-3 gap-4">
              {copy.stats.map((stat) => (
                <div key={stat.label} className="rounded-xl border border-border bg-card p-4 text-center">
                  <div className="text-2xl font-bold text-foreground">{stat.value}</div>
                  <div className="mt-1 text-xs text-muted-foreground">{stat.label}</div>
                </div>
              ))}
            </div>

            <ul className="mt-8 space-y-3">
              {copy.bullets.map((bullet) => (
                <li key={bullet} className="flex gap-3 text-sm text-foreground">
                  <CheckCircle2 className="h-4 w-4 shrink-0 text-primary mt-0.5" />
                  {bullet}
                </li>
              ))}
            </ul>

            <div className="mt-8 flex flex-wrap gap-4">
              <Link
                href={copy.cta.href}
                className="inline-flex items-center gap-2 rounded-full bg-foreground px-6 py-3 text-sm font-semibold text-white hover:bg-foreground/90"
              >
                {copy.cta.label}
                <ArrowRight className="h-4 w-4" />
              </Link>
              <Link
                href={copy.blogLink.href}
                className="inline-flex items-center gap-2 rounded-full border border-border bg-card px-6 py-3 text-sm font-semibold text-foreground hover:bg-muted/50"
              >
                {copy.blogLink.label}
              </Link>
            </div>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 24 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className="grid gap-3 sm:grid-cols-2"
          >
            {copy.packs.map((pack, i) => (
              <div
                key={pack.name}
                className="rounded-xl border border-border bg-card p-5 shadow-sm"
              >
                <div className="text-xs font-semibold uppercase tracking-wider text-primary">
                  Department pack
                </div>
                <h3 className="mt-2 font-semibold text-foreground">{pack.name}</h3>
                <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{pack.description}</p>
              </div>
            ))}
          </motion.div>
        </div>
      </div>
    </section>
  )
}

export function UseCasesSection() {
  const copy = MARKETING_COPY.useCases

  return (
    <section className="relative py-24 lg:py-28 border-t border-border bg-card">
      <div className="mx-auto max-w-7xl px-6">
        <motion.div
          initial={{ opacity: 0, y: 24 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          className="mx-auto max-w-3xl text-center mb-12"
        >
          <div className="mb-4 inline-flex items-center gap-2 rounded-full border border-border bg-muted/50 px-4 py-2">
            <Workflow className="h-4 w-4 text-muted-foreground" />
            <span className="text-sm font-medium text-foreground">{copy.badge}</span>
          </div>
          <h2 className="text-3xl sm:text-4xl font-bold tracking-tight text-foreground">{copy.title}</h2>
          <p className="mt-4 text-lg text-muted-foreground">{copy.subtitle}</p>
        </motion.div>

        <div className="grid gap-6 sm:grid-cols-2">
          {copy.cases.map((useCase, i) => (
            <motion.div
              key={useCase.title}
              initial={{ opacity: 0, y: 16 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: i * 0.06 }}
              className="rounded-2xl border border-border p-6 hover:border-border transition-colors"
            >
              <div className="text-xs font-semibold uppercase tracking-wider text-primary">
                {useCase.department}
              </div>
              <h3 className="mt-2 text-xl font-semibold text-foreground">{useCase.title}</h3>
              <p className="mt-3 text-sm leading-relaxed text-muted-foreground">{useCase.description}</p>
              <div className="mt-4 flex flex-wrap gap-2">
                {useCase.surfaces.map((surface) => (
                  <span
                    key={surface}
                    className="rounded-full bg-muted px-3 py-1 text-xs font-medium text-muted-foreground"
                  >
                    {surface}
                  </span>
                ))}
              </div>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  )
}

export function GovernanceAiStackSection() {
  const copy = MARKETING_COPY.governanceStack

  return (
    <section className="relative py-24 lg:py-28 border-t border-border bg-muted/50">
      <div className="mx-auto max-w-7xl px-6">
        <motion.div
          initial={{ opacity: 0, y: 24 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          className="mx-auto max-w-3xl text-center mb-12"
        >
          <div className="mb-4 inline-flex items-center gap-2 rounded-full border border-rose-200 bg-rose-50 px-4 py-2">
            <Shield className="h-4 w-4 text-rose-600" />
            <span className="text-sm font-medium text-rose-700">{copy.badge}</span>
          </div>
          <h2 className="text-3xl sm:text-4xl font-bold tracking-tight text-foreground">{copy.title}</h2>
          <p className="mt-4 text-lg text-muted-foreground">{copy.subtitle}</p>
        </motion.div>

        <div className="grid gap-8 lg:grid-cols-2">
          <div>
            <h3 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground mb-4">Governance</h3>
            <div className="space-y-4">
              {copy.governance.map((item, i) => (
                <motion.div
                  key={item.title}
                  initial={{ opacity: 0, x: -12 }}
                  whileInView={{ opacity: 1, x: 0 }}
                  viewport={{ once: true }}
                  transition={{ delay: i * 0.06 }}
                  className="rounded-xl border border-border bg-card p-5"
                >
                  <h4 className="font-semibold text-foreground">{item.title}</h4>
                  <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{item.description}</p>
                </motion.div>
              ))}
            </div>
          </div>
          <div>
            <h3 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground mb-4">
              LLM and intelligence stack
            </h3>
            <div className="space-y-4">
              {copy.aiStack.map((item, i) => (
                <motion.div
                  key={item.title}
                  initial={{ opacity: 0, x: 12 }}
                  whileInView={{ opacity: 1, x: 0 }}
                  viewport={{ once: true }}
                  transition={{ delay: i * 0.06 }}
                  className="rounded-xl border border-border bg-card p-5"
                >
                  <h4 className="font-semibold text-foreground">{item.title}</h4>
                  <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{item.description}</p>
                </motion.div>
              ))}
            </div>
          </div>
        </div>

        <motion.div
          initial={{ opacity: 0, y: 12 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          className="mt-10 flex flex-wrap justify-center gap-6"
        >
          {copy.links.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              className="inline-flex items-center gap-2 text-sm font-medium text-primary hover:text-primary"
            >
              {link.label}
              <ArrowRight className="h-4 w-4" />
            </Link>
          ))}
        </motion.div>
      </div>
    </section>
  )
}
