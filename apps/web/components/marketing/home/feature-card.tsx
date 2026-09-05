"use client"

import Link from "next/link"
import { motion } from "framer-motion"
import { ChevronRight } from "lucide-react"
import {
  NucleoAgent,
  NucleoApproval,
  NucleoConnector,
  NucleoIntelligence,
  NucleoVoice,
  NucleoWorkflow,
} from "@/components/icons/nucleo/semantic"
import { cn } from "@/lib/utils"
import type { ComponentType, SVGProps } from "react"

type IconComp = ComponentType<SVGProps<SVGSVGElement> & { size?: number | string }>

const FEATURE_ICONS: IconComp[] = [
  NucleoAgent,
  NucleoConnector,
  NucleoAgent,
  NucleoWorkflow,
  NucleoApproval,
  NucleoVoice,
  NucleoIntelligence,
]

/** Intelligence-leaning card indices */
const INTELLIGENCE_INDICES = new Set([0, 2, 6])
const OPERATIONAL_INDICES = new Set([3, 4, 5])

export function FeatureCard({
  iconIndex,
  title,
  description,
  index,
}: {
  iconIndex: number
  title: string
  description: string
  index: number
}) {
  const Icon = FEATURE_ICONS[iconIndex] ?? NucleoAgent
  const intel = INTELLIGENCE_INDICES.has(iconIndex)
  const operational = OPERATIONAL_INDICES.has(iconIndex)

  return (
    <motion.div
      initial={{ opacity: 0, y: 28 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-8%" }}
      transition={{ delay: index * 0.07, duration: 0.45, ease: [0.22, 1, 0.36, 1] }}
      whileHover={{ y: -4, transition: { duration: 0.2 } }}
      className="group relative"
    >
      <div
        className={cn(
          "absolute -inset-px rounded-2xl opacity-0 transition-opacity duration-500 group-hover:opacity-100",
          intel
            ? "bg-gradient-to-b from-[color:var(--g-intelligence)]/25 to-transparent"
            : operational
              ? "bg-gradient-to-b from-[color:var(--g-emerald)]/20 to-transparent"
              : "bg-gradient-to-b from-primary/15 to-transparent",
        )}
      />
      <div
        className="g-material-panel relative h-full rounded-2xl border border-[color:var(--g-border-subtle)] p-6 transition-all duration-[var(--g-duration-state)] group-hover:border-[color:var(--g-border-active)]"
        style={{
          backgroundImage: "var(--g-material-panel)",
          boxShadow: "var(--highlight-edge), var(--g-shadow-surface)",
        }}
      >
        <div
          className={cn(
            "mb-5 inline-flex h-12 w-12 items-center justify-center rounded-xl ring-1 transition-all duration-[var(--g-duration-state)]",
            intel
              ? "bg-[color:var(--g-intelligence)]/12 ring-[color:var(--g-intelligence)]/30 group-hover:shadow-[var(--g-glow-intelligence)]"
              : operational
                ? "bg-[color:var(--g-emerald)]/12 ring-[color:var(--g-emerald)]/28 group-hover:shadow-[var(--g-glow-operational)]"
                : "bg-primary/10 ring-primary/20",
          )}
        >
          <Icon
            className={cn(
              "h-6 w-6",
              intel
                ? "text-[color:var(--g-intelligence)]"
                : operational
                  ? "text-[color:var(--g-emerald)]"
                  : "text-primary",
            )}
            strokeWidth={1.5}
          />
        </div>
        <h3 className="text-lg font-semibold tracking-tight text-foreground">{title}</h3>
        <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{description}</p>
        <Link
          href="/features"
          className={cn(
            "mt-5 inline-flex items-center text-sm font-medium opacity-0 transition-all duration-[var(--g-duration-state)] group-hover:opacity-100",
            intel ? "text-[color:var(--g-intelligence)]" : "text-primary",
          )}
        >
          <span>Learn more</span>
          <ChevronRight
            strokeWidth={1.5}
            className="ml-1 h-4 w-4 transition-transform group-hover:translate-x-0.5"
          />
        </Link>
      </div>
    </motion.div>
  )
}
