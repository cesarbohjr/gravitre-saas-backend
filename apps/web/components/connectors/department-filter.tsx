"use client"

import { motion, useReducedMotion } from "framer-motion"
import { ArrowLeft, Building2, LayoutList } from "lucide-react"
import { Illustration, type IllustrationName } from "@/components/gravitre/illustration"
import { cn } from "@/lib/utils"

export type ConnectorDepartmentId = "sales" | "marketing" | "operations" | "finance" | "support" | "engineering"

export type ConnectorDepartment = {
  id: ConnectorDepartmentId
  label: string
  sentence: string
  illustration: IllustrationName
  /** Catalog categories (lib/connectors CONNECTOR_CATEGORY_META) this team works in. */
  categories: readonly string[]
}

export const CONNECTOR_DEPARTMENTS: readonly ConnectorDepartment[] = [
  {
    id: "sales",
    label: "Sales",
    sentence: "Find leads and close more deals.",
    illustration: "dept-sales",
    categories: ["Sales / Prospecting", "CRM / Marketing"],
  },
  {
    id: "marketing",
    label: "Marketing",
    sentence: "Plan campaigns and reach buyers.",
    illustration: "dept-marketing",
    categories: ["CRM / Marketing", "Learning / Creative"],
  },
  {
    id: "operations",
    label: "Operations",
    sentence: "Keep work and teams moving daily.",
    illustration: "dept-operations",
    categories: ["Operations / Workflow", "HR / People", "Communication"],
  },
  {
    id: "finance",
    label: "Finance",
    sentence: "Track payments, spend and cash.",
    illustration: "dept-finance",
    categories: ["Payments / Finance"],
  },
  {
    id: "support",
    label: "Support",
    sentence: "Help customers on every channel.",
    illustration: "dept-support",
    categories: ["Customer Support", "Communication"],
  },
  {
    id: "engineering",
    label: "Engineering",
    sentence: "Ship code and fix incidents fast.",
    illustration: "dept-engineering",
    categories: ["DevOps / Incidents", "Storage / Dev / Infra"],
  },
]

export function connectorDepartment(id: ConnectorDepartmentId | null) {
  return id ? CONNECTOR_DEPARTMENTS.find((d) => d.id === id) ?? null : null
}

/** True when a connector's catalog category belongs to the department (no department = every connector). */
export function connectorInDepartment(category: string | undefined, id: ConnectorDepartmentId | null) {
  const department = connectorDepartment(id)
  if (!department) return true
  return Boolean(category && department.categories.includes(category))
}

export type ConnectorsViewMode = "all" | "departments"

/** Top-of-page toggle between the full list and browsing by department. */
export function ConnectorsViewToggle({
  value,
  onChange,
  className,
}: {
  value: ConnectorsViewMode
  onChange: (value: ConnectorsViewMode) => void
  className?: string
}) {
  const options = [
    { value: "all" as const, label: "All connectors", icon: LayoutList },
    { value: "departments" as const, label: "By department", icon: Building2 },
  ]
  return (
    <div
      role="radiogroup"
      aria-label="Connectors view"
      className={cn("inline-flex shrink-0 items-center rounded-full border border-border bg-secondary p-0.5", className)}
      data-testid="connectors-view-toggle"
    >
      {options.map(({ value: option, label, icon: Icon }) => {
        const active = value === option
        return (
          <button
            key={option}
            type="button"
            role="radio"
            aria-checked={active}
            onClick={() => onChange(option)}
            className={cn(
              "flex min-h-11 items-center gap-1.5 rounded-full px-3 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring sm:min-h-8",
              active ? "bg-background text-foreground shadow-sm" : "text-muted-foreground hover:text-foreground",
            )}
          >
            <Icon className="h-3.5 w-3.5" aria-hidden />
            {label}
          </button>
        )
      })}
    </div>
  )
}

/** Department image cards, shown on their own; picking one opens that department's connectors. */
export function ConnectorDepartmentCards({
  counts,
  onSelect,
  onShowAll,
}: {
  counts: Record<ConnectorDepartmentId, number>
  onSelect: (id: ConnectorDepartmentId) => void
  onShowAll: () => void
}) {
  const reduceMotion = useReducedMotion()
  return (
    <section aria-labelledby="connector-departments-heading" className="mx-auto max-w-[1040px]" data-testid="connector-department-cards">
      <div className="mb-4 flex flex-wrap items-baseline justify-between gap-3">
        <div>
          <h2 id="connector-departments-heading" className="text-[15px] font-semibold text-foreground">
            Departments
          </h2>
          <p className="mt-0.5 text-sm text-muted-foreground">Pick a team to see the systems it works in.</p>
        </div>
        <button
          type="button"
          onClick={onShowAll}
          className="rounded-md text-sm font-medium text-[color:var(--g-emerald-deep)] hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          Show all connectors
        </button>
      </div>
      <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 xl:grid-cols-3 xl:gap-8">
        {CONNECTOR_DEPARTMENTS.map((department, index) => {
          const count = counts[department.id] ?? 0
          return (
            <motion.button
              key={department.id}
              type="button"
              onClick={() => onSelect(department.id)}
              initial={reduceMotion ? false : { opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              whileHover={reduceMotion ? undefined : { y: -3 }}
              whileTap={reduceMotion ? undefined : { scale: 0.99 }}
              transition={{ duration: 0.35, ease: "easeOut", delay: reduceMotion ? 0 : index * 0.04 }}
              className="group overflow-hidden rounded-2xl border border-border bg-card text-left shadow-sm transition-shadow hover:shadow-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              data-department={department.id}
              aria-label={`${department.label}: ${count} connected`}
            >
              <div className="overflow-hidden bg-muted">
                <motion.div
                  animate={reduceMotion ? undefined : { y: [0, -3, 0] }}
                  transition={{ duration: 6, repeat: Infinity, ease: "easeInOut", delay: index * 0.7 }}
                  className="transition-transform duration-500 ease-out group-hover:scale-[1.03]"
                >
                  <Illustration name={department.illustration} width={420} className="!w-full rounded-none" />
                </motion.div>
              </div>
              <div className="px-5 py-4">
                <div className="flex items-center justify-between gap-3">
                  <p className="text-[15px] font-semibold text-foreground">{department.label}</p>
                  <span className="shrink-0 rounded-full bg-secondary px-2 py-0.5 text-xs font-medium tabular-nums text-muted-foreground">
                    {count} connected
                  </span>
                </div>
                <p className="mt-1 text-sm text-muted-foreground">{department.sentence}</p>
              </div>
            </motion.button>
          )
        })}
      </div>
    </section>
  )
}

/** Header above a department's connectors: where you are, and the way back to the cards. */
export function ConnectorDepartmentBar({
  department: id,
  onBack,
  onShowAll,
}: {
  department: ConnectorDepartmentId
  onBack: () => void
  onShowAll: () => void
}) {
  const department = connectorDepartment(id)
  if (!department) return null
  return (
    <div className="mb-5 flex flex-wrap items-center justify-between gap-3" data-testid="connector-department-bar">
      <div className="flex min-w-0 items-center gap-3">
        <button
          type="button"
          onClick={onBack}
          className="inline-flex min-h-9 items-center gap-1.5 rounded-full border border-border bg-card px-3 text-sm font-medium text-foreground transition-colors hover:bg-secondary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          <ArrowLeft className="h-3.5 w-3.5" aria-hidden />
          Departments
        </button>
        <div className="min-w-0">
          <p className="text-[15px] font-semibold text-foreground">{department.label}</p>
          <p className="text-sm text-muted-foreground">{department.sentence}</p>
        </div>
      </div>
      <button
        type="button"
        onClick={onShowAll}
        className="rounded-md text-sm font-medium text-[color:var(--g-emerald-deep)] hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        Show all connectors
      </button>
    </div>
  )
}
