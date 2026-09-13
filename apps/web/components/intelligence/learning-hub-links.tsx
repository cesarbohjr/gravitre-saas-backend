"use client"

import Link from "next/link"
import { APP_ROUTES } from "@/lib/app-routes"
import { TYPE } from "@/lib/design-system"
import { cn } from "@/lib/utils"
import { ArrowRight, Brain, ChartLineUp, Cpu } from "@phosphor-icons/react"

const LINKS = [
  {
    href: APP_ROUTES.intelligenceMemory,
    title: "Org memory",
    description: "Approved knowledge and promoted memories feeding learning.",
    icon: Brain,
  },
  {
    href: APP_ROUTES.intelligenceReports,
    title: "Outcome reports",
    description: "Measured results and department scorecards.",
    icon: ChartLineUp,
  },
  {
    href: APP_ROUTES.training,
    title: "Model training",
    description: "Improve models from real usage — separate from business learning claims.",
    icon: Cpu,
  },
] as const

export function LearningHubLinks({ className }: { className?: string }) {
  return (
    <section className={cn("space-y-3", className)} aria-labelledby="learning-hub-links-heading">
      <div>
        <p className={TYPE.eyebrow}>Explore</p>
        <h2 id="learning-hub-links-heading" className={TYPE.sectionTitle}>
          Related intelligence surfaces
        </h2>
      </div>
      <div className="grid gap-3 md:grid-cols-3">
        {LINKS.map((link) => {
          const Icon = link.icon
          return (
            <Link
              key={link.href}
              href={link.href}
              className="group rounded-[var(--np-radius-md)] border border-divide bg-[color:var(--g-surface-1)] p-4 transition-colors hover:border-[color:var(--g-brand-border)]"
            >
              <Icon className="h-5 w-5 text-[color:var(--g-intelligence)]" aria-hidden />
              <p className={cn(TYPE.cardTitle, "mt-2")}>{link.title}</p>
              <p className={cn(TYPE.meta, "mt-1")}>{link.description}</p>
              <span className="mt-2 inline-flex items-center gap-1 text-xs font-medium text-[color:var(--g-brand)] opacity-0 transition-opacity group-hover:opacity-100">
                Open
                <ArrowRight className="h-3 w-3" aria-hidden />
              </span>
            </Link>
          )
        })}
      </div>
    </section>
  )
}
