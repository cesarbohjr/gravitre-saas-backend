"use client"

import Link from "next/link"
import { motion } from "framer-motion"
import { ArrowRight, Brain, Database, Shield, Sparkles, Workflow, Cpu, Lock } from "lucide-react"
import { FeaturesLegacyContent } from "@/components/marketing/features/legacy-page"

const orbitNodes = [
  { icon: Database, label: "Connectors", tone: "text-blue-600 bg-blue-100 border-blue-200", angle: 0 },
  { icon: Sparkles, label: "Insights", tone: "text-amber-600 bg-amber-100 border-amber-200", angle: 90 },
  { icon: Shield, label: "Approvals", tone: "text-rose-600 bg-rose-100 border-rose-200", angle: 180 },
  { icon: Workflow, label: "Workflows", tone: "text-primary bg-primary/15 border-primary/20", angle: 270 },
] as const

const specPills = [
  { icon: Cpu, label: "Built-in ML catalog" },
  { icon: Brain, label: "Org-scoped memory" },
  { icon: Lock, label: "Approval before writes" },
  { icon: Shield, label: "Full audit trail" },
] as const

function IntelligenceCore() {
  return (
    <div className="relative mx-auto flex h-80 w-80 items-center justify-center sm:h-96 sm:w-96">
      {/* Concentric rings */}
      {[0, 1, 2].map((ring) => (
        <motion.div
          key={ring}
          className="absolute rounded-full border border-primary/20/70"
          style={{ inset: ring * 44 }}
          animate={{ rotate: ring % 2 === 0 ? 360 : -360 }}
          transition={{ duration: 40 + ring * 12, repeat: Number.POSITIVE_INFINITY, ease: "linear" }}
        />
      ))}

      {/* Soft glow */}
      <div className="absolute inset-16 rounded-full bg-gradient-to-br from-emerald-200/50 to-teal-200/40 blur-2xl" />

      {/* Orbiting nodes */}
      <motion.div
        className="absolute inset-0"
        animate={{ rotate: 360 }}
        transition={{ duration: 32, repeat: Number.POSITIVE_INFINITY, ease: "linear" }}
      >
        {orbitNodes.map((node) => {
          const Icon = node.icon
          const rad = (node.angle * Math.PI) / 180
          const radius = 46 // percentage from center
          const x = 50 + radius * Math.cos(rad)
          const y = 50 + radius * Math.sin(rad)
          return (
            <motion.div
              key={node.label}
              className={`absolute flex h-14 w-14 -translate-x-1/2 -translate-y-1/2 items-center justify-center rounded-2xl border shadow-sm ${node.tone}`}
              style={{ left: `${x}%`, top: `${y}%` }}
              animate={{ rotate: -360 }}
              transition={{ duration: 32, repeat: Number.POSITIVE_INFINITY, ease: "linear" }}
            >
              <Icon className="h-6 w-6" />
            </motion.div>
          )
        })}
      </motion.div>

      {/* Center core */}
      <motion.div
        className="relative z-10 flex h-28 w-28 flex-col items-center justify-center rounded-full bg-gradient-to-br from-emerald-600 to-teal-500 text-white shadow-xl shadow-emerald-500/30"
        animate={{ scale: [1, 1.05, 1] }}
        transition={{ duration: 3.5, repeat: Number.POSITIVE_INFINITY, ease: "easeInOut" }}
      >
        <Brain className="h-9 w-9" />
        <span className="mt-1 text-xs font-semibold tracking-wide">GIBE</span>
      </motion.div>
    </div>
  )
}

export function TechnologyPage() {
  return (
    <div className="bg-card">
      {/* Hero */}
      <section className="relative overflow-hidden pt-28 pb-20 sm:pt-32">
        <div className="absolute inset-0 bg-gradient-to-b from-primary/10 via-white to-white" />
        <div className="absolute -top-24 right-0 h-72 w-72 rounded-full bg-teal-200/30 blur-3xl" />
        <div className="absolute top-32 -left-16 h-64 w-64 rounded-full bg-emerald-200/30 blur-3xl" />

        <div className="relative mx-auto grid max-w-7xl items-center gap-12 px-6 lg:grid-cols-2">
          <motion.div
            initial={{ opacity: 0, y: 24 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
          >
            <div className="mb-5 inline-flex items-center gap-2 rounded-full border border-primary/20 bg-primary/10 px-4 py-2">
              <Cpu className="h-4 w-4 text-primary" />
              <span className="text-sm font-medium text-primary">Platform technology</span>
            </div>
            <h1 className="text-4xl font-bold tracking-tight text-foreground sm:text-5xl lg:text-6xl text-balance">
              The engine behind every{" "}
              <span className="bg-gradient-to-r from-emerald-600 to-teal-500 bg-clip-text text-transparent">
                decision and write
              </span>
            </h1>
            <p className="mt-6 max-w-xl text-lg leading-relaxed text-muted-foreground text-pretty">
              GIBE — the Gravitre Intelligent Business Engine — learns from your connected stack and routes
              every action through governed, human-approved execution. Intelligence and control, one system.
            </p>

            <div className="mt-8 flex flex-wrap gap-2.5">
              {specPills.map((pill) => {
                const Icon = pill.icon
                return (
                  <span
                    key={pill.label}
                    className="inline-flex items-center gap-2 rounded-full border border-border bg-card px-3.5 py-2 text-sm font-medium text-foreground shadow-sm"
                  >
                    <Icon className="h-4 w-4 text-primary" />
                    {pill.label}
                  </span>
                )
              })}
            </div>

            <div className="mt-9 flex flex-wrap gap-4">
              <Link
                href="/get-started"
                className="inline-flex items-center gap-2 rounded-full bg-foreground px-6 py-3 text-sm font-semibold text-white transition-colors hover:bg-foreground/90"
              >
                Start free
                <ArrowRight className="h-4 w-4" />
              </Link>
              <Link
                href="/features/marketplace"
                className="inline-flex items-center gap-2 rounded-full border border-border bg-card px-6 py-3 text-sm font-semibold text-foreground transition-colors hover:bg-muted/50"
              >
                Explore the marketplace
              </Link>
            </div>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, scale: 0.92 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.7, delay: 0.1, ease: [0.16, 1, 0.3, 1] }}
            className="flex justify-center"
          >
            <IntelligenceCore />
          </motion.div>
        </div>
      </section>

      {/* GIBE intelligence sections (reused, hero/tail suppressed) */}
      <FeaturesLegacyContent section="intelligence" showHero={false} showTail={false} />

      {/* Governance + AI stack (reused, hero/tail suppressed) */}
      <FeaturesLegacyContent section="governance" showHero={false} showTail={false} />

      {/* CTA */}
      <section className="relative overflow-hidden border-t border-border bg-gradient-to-b from-white to-primary/10 py-24">
        <div className="mx-auto max-w-3xl px-6 text-center">
          <h2 className="text-3xl font-bold tracking-tight text-foreground sm:text-4xl text-balance">
            Intelligence you can audit, execution you can trust
          </h2>
          <p className="mt-4 text-lg text-muted-foreground text-pretty">
            See how GIBE and governed execution work together across your connected tools.
          </p>
          <div className="mt-8 flex flex-wrap justify-center gap-4">
            <Link
              href="/get-started"
              className="inline-flex items-center gap-2 rounded-full bg-primary px-7 py-3.5 text-sm font-semibold text-white transition-colors hover:bg-primary/100"
            >
              Get started
              <ArrowRight className="h-4 w-4" />
            </Link>
            <Link
              href="/features"
              className="inline-flex items-center gap-2 rounded-full border border-border bg-card px-7 py-3.5 text-sm font-semibold text-foreground transition-colors hover:bg-muted/50"
            >
              Back to platform features
            </Link>
          </div>
        </div>
      </section>
    </div>
  )
}
