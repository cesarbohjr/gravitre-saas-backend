"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import { ChevronRight } from "lucide-react"
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from "@/components/ui/breadcrumb"
import { APP_ROUTES } from "@/lib/app-routes"
import { SURFACE_COPY } from "@/lib/surface-copy"
import { ConnectorIcon } from "@/components/gravitre/connector-icon"
import { fallbackEntityLabel, isUuidPathSegment } from "@/lib/breadcrumb-entity"

interface AppBreadcrumbsProps {
  /** Human-readable label for the current dynamic segment (e.g. connector name). */
  entityLabel?: string
  /** Vendor key for connector detail breadcrumbs. */
  entityVendor?: string
}

const LABELS: Record<string, string> = {
  home: "Home",
  welcome: "Getting Started",
  ai: "Chat",
  "command-center": "Chat",
  operator: "Chat",
  assistant: "Workspace Chat",
  search: "Universal Search",
  chat: "Universal Search",
  agents: "AI Team",
  "multi-agent-run": "Multi-Agent Run",
  swarm: "Multi-Agent Run",
  intelligence: SURFACE_COPY.insights.title,
  admin: "Admin",
  marketplace: "Marketplace",
  workflows: "Workflows",
  connectors: "Connectors",
  sources: "Sources",
  training: SURFACE_COPY.training.title,
  models: SURFACE_COPY.models.title,
  "built-in": SURFACE_COPY.builtInModels.title,
  runs: "Runs",
  schedules: "Schedules",
  approvals: "Approvals",
  metrics: "Metrics",
  audit: "Audit trail",
  settings: "Settings",
  environments: "Environments",
  assignments: "Assignments",
  goals: "Goals",
  memory: SURFACE_COPY.hubLinks.memory.title,
  reports: SURFACE_COPY.hubLinks.reports.title,
  performance: SURFACE_COPY.adminTabs.performance,
  learning: SURFACE_COPY.learning.title,
  outcomes: SURFACE_COPY.adminTabs.outcomes,
}

function labelForSegment(
  segment: string,
  index: number,
  segments: string[],
  entityLabel?: string,
): string {
  if (segment in LABELS) return LABELS[segment]!
  if (isUuidPathSegment(segment)) {
    if (index === segments.length - 1 && entityLabel?.trim()) {
      return entityLabel.trim()
    }
    return fallbackEntityLabel(segments[index - 1])
  }
  if (index === segments.length - 1 && segments[0] === "agents" && index === 1) return "Agent"
  if (segments[0] === "intelligence" && segment === "agents" && index === 1) return SURFACE_COPY.hubLinks.agents.title
  if (segments[0] === "models" && segment === "built-in" && index === 1) return SURFACE_COPY.builtInModels.title
  if (segments[0] === "intelligence" && segment === "models" && index === 1) return SURFACE_COPY.builtInModels.title
  return segment.replace(/-/g, " ").replace(/\b\w/g, (char) => char.toUpperCase())
}

export function AppBreadcrumbs({ entityLabel, entityVendor }: AppBreadcrumbsProps = {}) {
  const pathname = usePathname()
  const segments = pathname.split("/").filter(Boolean)

  if (segments.length <= 1) return null

  const crumbs = segments.map((segment, index) => {
    const href = `/${segments.slice(0, index + 1).join("/")}`
    return {
      href,
      label: labelForSegment(segment, index, segments, entityLabel),
      isLast: index === segments.length - 1,
    }
  })

  return (
    <Breadcrumb className="mb-4 hidden sm:block">
      <BreadcrumbList>
        <BreadcrumbItem>
          <BreadcrumbLink asChild>
            <Link href={APP_ROUTES.home}>Home</Link>
          </BreadcrumbLink>
        </BreadcrumbItem>
        {crumbs.map((crumb) => (
          <span key={crumb.href} className="contents">
            <BreadcrumbSeparator>
              <ChevronRight className="h-3.5 w-3.5" />
            </BreadcrumbSeparator>
            <BreadcrumbItem>
              {crumb.isLast ? (
                <BreadcrumbPage className="inline-flex items-center gap-2">
                  {segments[0] === "connectors" &&
                  isUuidPathSegment(segments[segments.length - 1] ?? "") &&
                  entityVendor ? (
                    <ConnectorIcon vendor={entityVendor} size="xs" showStatusIndicator={false} />
                  ) : null}
                  {crumb.label}
                </BreadcrumbPage>
              ) : (
                <BreadcrumbLink asChild>
                  <Link href={crumb.href}>{crumb.label}</Link>
                </BreadcrumbLink>
              )}
            </BreadcrumbItem>
          </span>
        ))}
      </BreadcrumbList>
    </Breadcrumb>
  )
}
