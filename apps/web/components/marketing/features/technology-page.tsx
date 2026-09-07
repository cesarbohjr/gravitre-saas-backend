"use client"

import Link from "next/link"
import { motion } from "framer-motion"
import { Brain, Database, Shield, Sparkles, Workflow, Cpu, Lock } from "lucide-react"
import { FeaturesLegacyContent } from "@/components/marketing/features/legacy-page"
import { Button } from "@/components/marketing/nodus/button"
import { Container } from "@/components/marketing/nodus/container"
import { DivideX } from "@/components/marketing/nodus/divide"
import { MarketingPageEndCta, MarketingPageHero } from "@/components/marketing/nodus/page-shell"

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
    <div className="bg-white">
      <MarketingPageHero
        badge="Platform technology"
        title={
          <>
            The engine inside the{" "}
            <span className="text-brand">one brain</span>
          </>
        }
        description="GIBE — the Gravitre Intelligent Business Engine — learns from your connected stack and routes actions through governed, human-approved execution. Memory, models, and judgment for the same brain that powers Gravitre AI, agents, and workflows."
      >
        <div className="mt-8 flex flex-wrap items-center justify-center gap-2.5">
          {specPills.map((pill) => {
            const Icon = pill.icon
            return (
              <span
                key={pill.label}
                className="inline-flex items-center gap-2 rounded-full border border-divide bg-gray-50 px-3.5 py-2 text-sm font-medium text-charcoal-700"
              >
                <Icon className="h-4 w-4 text-brand" />
                {pill.label}
              </span>
            )
          })}
        </div>
        <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
          <Button as={Link} href="/get-started">
            Start free
          </Button>
          <Button as={Link} href="/features/marketplace" variant="secondary">
            Explore the marketplace
          </Button>
        </div>
      </MarketingPageHero>

      <DivideX />

      <Container className="border-divide flex justify-center border-x px-4 py-16 md:px-8">
        <IntelligenceCore />
      </Container>

      <DivideX />

      {/* GIBE intelligence sections (reused, hero/tail suppressed) */}
      <FeaturesLegacyContent section="intelligence" showHero={false} showTail={false} />

      {/* Governance + AI stack (reused, hero/tail suppressed) */}
      <FeaturesLegacyContent section="governance" showHero={false} showTail={false} />

      <MarketingPageEndCta />
    </div>
  )
}
