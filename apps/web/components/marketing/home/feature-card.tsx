"use client"

import { motion } from "framer-motion"
import {
  BarChart3,
  Bot,
  ChevronRight,
  Shield,
  Users,
  Workflow,
  Zap,
  type LucideIcon,
} from "lucide-react"

const FEATURE_ICONS: LucideIcon[] = [Bot, Users, Workflow, Shield, Zap, BarChart3]

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
  return (
    <motion.div
      initial={{ opacity: 0, y: 30 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true }}
      transition={{ delay: index * 0.1 }}
      whileHover={{ y: -5, transition: { duration: 0.2 } }}
      className="group relative"
    >
      <div className="absolute -inset-px rounded-2xl bg-gradient-to-b from-emerald-100 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-500" />
      <div className="relative h-full rounded-2xl border border-zinc-200 bg-white p-6 shadow-sm transition-all group-hover:border-zinc-300 group-hover:shadow-lg">
        <div className="mb-4 inline-flex h-12 w-12 items-center justify-center rounded-xl bg-gradient-to-br from-emerald-100 to-emerald-50 ring-1 ring-emerald-200 group-hover:ring-emerald-300 transition-all">
          <Icon className="h-6 w-6 text-emerald-600" strokeWidth={1.5} />
        </div>
        <h3 className="text-lg font-semibold text-zinc-900 group-hover:text-emerald-900 transition-colors">{title}</h3>
        <p className="mt-2 text-sm text-zinc-600 leading-relaxed">{description}</p>
        <div className="mt-4 flex items-center text-sm text-emerald-600 font-medium opacity-0 group-hover:opacity-100 transition-opacity">
          <span>Learn more</span>
          <ChevronRight strokeWidth={1.5} className="ml-1 h-4 w-4" />
        </div>
      </div>
    </motion.div>
  )
}
