import type { ComponentType, SVGProps } from "react"
import {
  Building,
  Cube,
  Storefront,
  TreeStructure,
  User,
  UsersThree,
} from "@phosphor-icons/react"
import { NucleoAgent, NucleoIntelligence, NucleoWorkflow } from "@/components/icons/nucleo/semantic"

type EntityIcon = ComponentType<SVGProps<SVGSVGElement>>

export type EntityVisualSpec = {
  icon: EntityIcon
  surfaceClass: string
  iconClass: string
  borderClass: string
}

const DEFAULT: EntityVisualSpec = {
  icon: TreeStructure,
  surfaceClass: "bg-[color:var(--g-surface-1)]",
  iconClass: "text-[color:var(--g-text-muted)]",
  borderClass: "border-divide",
}

/** Restrained semantic styling per entity type (Nodus light language). */
export function entityVisualSpec(entityType: string, isSeeded: boolean): EntityVisualSpec {
  if (isSeeded) {
    return {
      icon: TreeStructure,
      surfaceClass: "bg-[color:var(--g-brand-soft)]/40",
      iconClass: "text-[color:var(--g-brand)]",
      borderClass: "border-[color:var(--g-brand)]/35",
    }
  }

  const t = entityType.trim().toLowerCase()
  const map: Record<string, EntityVisualSpec> = {
    company: {
      icon: Building,
      surfaceClass: "bg-emerald-50/80 dark:bg-emerald-950/20",
      iconClass: "text-emerald-700 dark:text-emerald-300",
      borderClass: "border-emerald-200/80 dark:border-emerald-800/50",
    },
    customer: {
      icon: UsersThree,
      surfaceClass: "bg-cyan-50/80 dark:bg-cyan-950/20",
      iconClass: "text-cyan-700 dark:text-cyan-300",
      borderClass: "border-cyan-200/80 dark:border-cyan-800/50",
    },
    employee: {
      icon: User,
      surfaceClass: "bg-indigo-50/80 dark:bg-indigo-950/20",
      iconClass: "text-indigo-700 dark:text-indigo-300",
      borderClass: "border-indigo-200/80 dark:border-indigo-800/50",
    },
    person: {
      icon: User,
      surfaceClass: "bg-indigo-50/80 dark:bg-indigo-950/20",
      iconClass: "text-indigo-700 dark:text-indigo-300",
      borderClass: "border-indigo-200/80 dark:border-indigo-800/50",
    },
    contact: {
      icon: User,
      surfaceClass: "bg-indigo-50/80 dark:bg-indigo-950/20",
      iconClass: "text-indigo-700 dark:text-indigo-300",
      borderClass: "border-indigo-200/80 dark:border-indigo-800/50",
    },
    vendor: {
      icon: Storefront,
      surfaceClass: "bg-sky-50/80 dark:bg-sky-950/20",
      iconClass: "text-sky-700 dark:text-sky-300",
      borderClass: "border-sky-200/80 dark:border-sky-800/50",
    },
    product: {
      icon: Cube,
      surfaceClass: "bg-violet-50/80 dark:bg-violet-950/20",
      iconClass: "text-violet-700 dark:text-violet-300",
      borderClass: "border-violet-200/80 dark:border-violet-800/50",
    },
    agent: {
      icon: NucleoAgent as EntityIcon,
      surfaceClass: "bg-[color:var(--g-brand-soft)]/50",
      iconClass: "text-[color:var(--g-brand)]",
      borderClass: "border-[color:var(--g-brand)]/30",
    },
    workflow_run: {
      icon: NucleoWorkflow as EntityIcon,
      surfaceClass: "bg-teal-50/80 dark:bg-teal-950/20",
      iconClass: "text-teal-700 dark:text-teal-300",
      borderClass: "border-teal-200/80 dark:border-teal-800/50",
    },
    glossary_term: {
      icon: NucleoIntelligence as EntityIcon,
      surfaceClass: "bg-amber-50/60 dark:bg-amber-950/15",
      iconClass: "text-amber-800 dark:text-amber-200",
      borderClass: "border-amber-200/70 dark:border-amber-800/40",
    },
    department: {
      icon: Building,
      surfaceClass: "bg-slate-50/80 dark:bg-slate-900/30",
      iconClass: "text-slate-700 dark:text-slate-300",
      borderClass: "border-slate-200/80 dark:border-slate-700/50",
    },
  }

  return map[t] ?? DEFAULT
}

export function clusterVisualSpec(entityType: string): EntityVisualSpec {
  const base = entityVisualSpec(entityType, false)
  return {
    ...base,
    icon: UsersThree,
    surfaceClass: "bg-cyan-50/90 dark:bg-cyan-950/25",
    borderClass: "border-cyan-300/70 dark:border-cyan-700/50 border-dashed",
  }
}
