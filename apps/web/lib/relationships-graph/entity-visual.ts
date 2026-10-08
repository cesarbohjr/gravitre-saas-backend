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
      surfaceClass: "bg-success/10",
      iconClass: "text-success-text",
      borderClass: "border-success/30",
    },
    customer: {
      icon: UsersThree,
      surfaceClass: "bg-info/10",
      iconClass: "text-info",
      borderClass: "border-info/30",
    },
    employee: {
      icon: User,
      surfaceClass: "bg-intelligence-text/10",
      iconClass: "text-intelligence-text",
      borderClass: "border-intelligence-text/30",
    },
    person: {
      icon: User,
      surfaceClass: "bg-intelligence-text/10",
      iconClass: "text-intelligence-text",
      borderClass: "border-intelligence-text/30",
    },
    contact: {
      icon: User,
      surfaceClass: "bg-intelligence-text/10",
      iconClass: "text-intelligence-text",
      borderClass: "border-intelligence-text/30",
    },
    vendor: {
      icon: Storefront,
      surfaceClass: "bg-info/10",
      iconClass: "text-info",
      borderClass: "border-info/30",
    },
    product: {
      icon: Cube,
      surfaceClass: "bg-chart-4/10",
      iconClass: "text-chart-4",
      borderClass: "border-chart-4/30",
    },
    agent: {
      icon: NucleoAgent as EntityIcon,
      surfaceClass: "bg-[color:var(--g-brand-soft)]/50",
      iconClass: "text-[color:var(--g-brand)]",
      borderClass: "border-[color:var(--g-brand)]/30",
    },
    workflow_run: {
      icon: NucleoWorkflow as EntityIcon,
      surfaceClass: "bg-brand-soft/60",
      iconClass: "text-brand-text",
      borderClass: "border-brand/30",
    },
    glossary_term: {
      icon: NucleoIntelligence as EntityIcon,
      surfaceClass: "bg-warning/10",
      iconClass: "text-warning-text",
      borderClass: "border-warning/30",
    },
    department: {
      icon: Building,
      surfaceClass: "bg-muted/60",
      iconClass: "text-muted-foreground",
      borderClass: "border-border",
    },
  }

  return map[t] ?? DEFAULT
}

export function clusterVisualSpec(entityType: string): EntityVisualSpec {
  const base = entityVisualSpec(entityType, false)
  return {
    ...base,
    icon: UsersThree,
    surfaceClass: "bg-info/15",
    borderClass: "border-info/40 border-dashed",
  }
}
