"use client"

import { motion } from "framer-motion"
import {
  BarChart3,
  Bot,
  Chrome,
  ChevronRight,
  Shield,
  Users,
  Workflow,
  Zap,
  type LucideIcon,
} from "lucide-react"
import { cn } from "@/lib/utils"

const FEATURE_ICONS: LucideIcon[] = [Bot, Chrome, Users, Workflow, Shield, Zap, BarChart3]

/** Intelligence-leaning card indices (Observe / GIBE-adjacent storytelling). */
const INTELLIGENCE_INDICES = new Set([0, 2, 4])

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
  const Icon = FEATURE_ICONS[iconIndex] ?? Bot
  const intel = INTELLIGENCE_INDICES.has(iconIndex)

  return (
    <motion.div
      initial={{ opacity: 0, y: 24 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true }}
      transition={{ delay: index * 0.08, duration: 0.35, ease: [0.22, 1, 0.36, 1] }}
      whileHover={{ y: -3, transition: { duration: 0.18 } }}
      className="group relative"
    >
      <div
        className={cn(
          "absolute -inset-px rounded-2xl opacity-0 transition-opacity duration-500 group-hover:opacity-100",
          intel
            ? "bg-gradient-to-b from-[color:var(--g-intelligence)]/20 to-transparent"
            : "bg-gradient-to-b from-primary/15 to-transparent",
        )}
      />
      <div
        className="relative h-full rounded-2xl border border-[color:var(--g-border-subtle)] bg-[color:var(--g-surface-1)] p-6 transition-all duration-[var(--g-duration-state)] group-hover:border-[color:var(--g-border-active)]"
        style={{
          boxShadow: "var(--highlight-edge), var(--g-shadow-surface)",
        }}
      >
        <div
          className={cn(
            "mb-4 inline-flex h-12 w-12 items-center justify-center rounded-xl ring-1 transition-all duration-[var(--g-duration-state)]",
            intel
              ? "bg-[color:var(--g-intelligence)]/10 ring-[color:var(--g-intelligence)]/25 group-hover:ring-[color:var(--g-intelligence)]/40"
              : "bg-primary/10 ring-primary/20 group-hover:ring-primary/35",
          )}
        >
          <Icon
            className={cn("h-6 w-6", intel ? "text-[color:var(--g-intelligence)]" : "text-primary")}
            strokeWidth={1.5}
          />
        </div>
        <h3 className="text-lg font-semibold text-foreground transition-colors duration-[var(--g-duration-micro)] group-hover:text-foreground">
          {title}
        </h3>
        <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{description}</p>
        <div
          className={cn(
            "mt-4 flex items-center text-sm font-medium opacity-0 transition-opacity duration-[var(--g-duration-state)] group-hover:opacity-100",
            intel ? "text-[color:var(--g-intelligence)]" : "text-primary",
          )}
        >
          <span>Learn more</span>
          <ChevronRight strokeWidth={1.5} className="ml-1 h-4 w-4" />
        </div>
      </div>
    </motion.div>
  )
}
