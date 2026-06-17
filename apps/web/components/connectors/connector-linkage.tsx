"use client"

import { useMemo } from "react"
import Link from "next/link"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import {
  Workflow as WorkflowIcon,
  Plus,
  CheckCircle2,
  CircleDashed,
  AlertTriangle,
  ArrowRight,
  Sparkles,
} from "lucide-react"
import type { Workflow } from "@/types/api"
import type {
  VendorActionCatalog,
  ConnectorActionDefinition,
} from "@/lib/connector-actions"

interface ConnectorLinkageProps {
  vendor: string
  connectorStatus: string
  catalog?: VendorActionCatalog | null
  workflows?: Workflow[]
}

// Scans a free-form workflow definition for references to this vendor or its
// connector nodes. The backend stores definitions as opaque JSON, so we walk it
// defensively rather than relying on a fixed shape.
function workflowUsesVendor(workflow: Workflow, vendor: string): boolean {
  const needle = vendor.toLowerCase()
  const haystacks: unknown[] = [
    workflow.active_version?.definition,
    ...(workflow.versions?.map((v) => v.definition) ?? []),
  ]
  for (const def of haystacks) {
    if (!def) continue
    try {
      if (JSON.stringify(def).toLowerCase().includes(`"${needle}"`)) return true
      // looser match for "vendor.action" keys and substrings
      if (JSON.stringify(def).toLowerCase().includes(needle)) return true
    } catch {
      // ignore non-serializable definitions
    }
  }
  return false
}

function tierActions(catalog: VendorActionCatalog): ConnectorActionDefinition[] {
  return [
    ...catalog.tiers.v1.actions,
    ...catalog.tiers.v2.actions,
    ...catalog.tiers.v3.actions,
  ]
}

const TIER_LABEL: Record<string, string> = {
  v1: "Read",
  v2: "Write",
  v3: "Advanced",
}

export function ConnectorLinkage({ vendor, connectorStatus, catalog, workflows }: ConnectorLinkageProps) {
  const linkedWorkflows = useMemo(
    () => (workflows ?? []).filter((w) => workflowUsesVendor(w, vendor)),
    [workflows, vendor],
  )

  const actions = useMemo(() => (catalog ? tierActions(catalog) : []), [catalog])
  const readyCount = actions.filter((a) => a.implemented).length
  const plannedCount = actions.length - readyCount

  const isDisconnected = connectorStatus !== "connected"
  const referencedWhileDisconnected = isDisconnected && linkedWorkflows.length > 0

  return (
    <div className="space-y-6">
      {/* Disconnected-but-referenced warning */}
      {referencedWhileDisconnected ? (
        <div className="flex items-start gap-3 rounded-lg border border-amber-500/30 bg-amber-500/10 p-4">
          <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-amber-500" />
          <div className="flex-1">
            <p className="text-sm font-medium text-foreground">
              This connector is {connectorStatus} but used by {linkedWorkflows.length}{" "}
              {linkedWorkflows.length === 1 ? "workflow" : "workflows"}
            </p>
            <p className="mt-0.5 text-xs text-muted-foreground">
              Steps that call {vendor} will fail until the connection is restored. Reconnect to keep these workflows
              running.
            </p>
          </div>
        </div>
      ) : null}

      <div className="grid gap-6 md:grid-cols-2">
        {/* Action Readiness */}
        <Card className="bg-card border-border">
          <CardHeader className="pb-3">
            <div className="flex items-center justify-between">
              <CardTitle className="flex items-center gap-2 text-sm font-medium">
                <Sparkles className="h-4 w-4 text-emerald-500" />
                Action Readiness
              </CardTitle>
              {actions.length > 0 ? (
                <span className="text-xs text-muted-foreground">
                  {readyCount} ready{plannedCount > 0 ? ` · ${plannedCount} planned` : ""}
                </span>
              ) : null}
            </div>
            <CardDescription className="text-xs">
              Tools this connector can run as workflow steps
            </CardDescription>
          </CardHeader>
          <CardContent>
            {actions.length === 0 ? (
              <p className="py-6 text-center text-xs text-muted-foreground">
                No catalog actions are published for this vendor yet.
              </p>
            ) : (
              <div className="max-h-72 space-y-1.5 overflow-auto pr-1">
                {actions.map((action) => (
                  <div
                    key={action.tool}
                    className="flex items-center justify-between gap-2 rounded-md bg-secondary/30 px-2.5 py-2"
                  >
                    <div className="flex min-w-0 items-center gap-2">
                      {action.implemented ? (
                        <CheckCircle2 className="h-3.5 w-3.5 shrink-0 text-emerald-500" />
                      ) : (
                        <CircleDashed className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
                      )}
                      <div className="min-w-0">
                        <p className="truncate text-xs font-medium text-foreground">{action.name}</p>
                        <p className="truncate font-mono text-[10px] text-muted-foreground">{action.tool}</p>
                      </div>
                    </div>
                    <div className="flex shrink-0 items-center gap-1.5">
                      <span
                        className={cn(
                          "rounded px-1.5 py-0.5 text-[9px] font-medium uppercase tracking-wide",
                          action.tier === "v1"
                            ? "bg-sky-500/10 text-sky-500"
                            : action.tier === "v2"
                              ? "bg-violet-500/10 text-violet-400"
                              : "bg-amber-500/10 text-amber-500",
                        )}
                      >
                        {TIER_LABEL[action.tier] ?? action.tier}
                      </span>
                      {action.implemented ? (
                        <Button
                          asChild
                          variant="ghost"
                          size="sm"
                          className="h-6 gap-1 px-1.5 text-[10px] text-emerald-600 hover:text-emerald-700"
                        >
                          <Link
                            href={`/workflows/new/builder?vendor=${encodeURIComponent(vendor)}&action=${encodeURIComponent(action.tool)}`}
                          >
                            <Plus className="h-3 w-3" />
                            Add
                          </Link>
                        </Button>
                      ) : (
                        <span className="px-1.5 text-[10px] text-muted-foreground">Planned</span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Used in Workflows (live) */}
        <Card className="bg-card border-border">
          <CardHeader className="pb-3">
            <div className="flex items-center justify-between">
              <CardTitle className="flex items-center gap-2 text-sm font-medium">
                <WorkflowIcon className="h-4 w-4 text-sky-500" />
                Used in Workflows
              </CardTitle>
              <span className="text-xs text-muted-foreground">
                {linkedWorkflows.length} {linkedWorkflows.length === 1 ? "workflow" : "workflows"}
              </span>
            </div>
            <CardDescription className="text-xs">Workflows that reference this connector</CardDescription>
          </CardHeader>
          <CardContent>
            {linkedWorkflows.length === 0 ? (
              <div className="flex flex-col items-center gap-3 py-6 text-center">
                <p className="text-xs text-muted-foreground">No workflows use this connector yet.</p>
                {readyCount > 0 ? (
                  <Button asChild variant="outline" size="sm" className="gap-1.5">
                    <Link href={`/workflows/new/builder?vendor=${encodeURIComponent(vendor)}`}>
                      <Plus className="h-3.5 w-3.5" />
                      Build a workflow with {vendor}
                    </Link>
                  </Button>
                ) : null}
              </div>
            ) : (
              <div className="max-h-72 space-y-1.5 overflow-auto pr-1">
                {linkedWorkflows.map((workflow) => (
                  <Link
                    key={workflow.id}
                    href={`/workflows/${workflow.id}`}
                    className="flex items-center justify-between gap-2 rounded-md bg-secondary/30 px-2.5 py-2 transition-colors hover:bg-secondary/50"
                  >
                    <div className="flex min-w-0 items-center gap-2">
                      <div
                        className={cn(
                          "h-2 w-2 shrink-0 rounded-full",
                          workflow.status === "active" ? "bg-emerald-500" : "bg-amber-500",
                        )}
                      />
                      <span className="truncate text-sm font-medium text-foreground">{workflow.name}</span>
                    </div>
                    <ArrowRight className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
                  </Link>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Demo workflow install cards */}
      {catalog && catalog.demoWorkflows.length > 0 ? (
        <Card className="bg-card border-border">
          <CardHeader className="pb-3">
            <CardTitle className="flex items-center gap-2 text-sm font-medium">
              <Sparkles className="h-4 w-4 text-violet-400" />
              Starter Workflows
            </CardTitle>
            <CardDescription className="text-xs">
              Prebuilt {catalog.displayName} workflows you can install in one click
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {catalog.demoWorkflows.map((demo) => (
                <div
                  key={demo.id}
                  className="flex flex-col gap-2 rounded-lg border border-border bg-secondary/20 p-3"
                >
                  <div className="flex items-start justify-between gap-2">
                    <p className="text-sm font-medium text-foreground">{demo.name}</p>
                    <span
                      className={cn(
                        "shrink-0 rounded px-1.5 py-0.5 text-[9px] font-medium uppercase",
                        demo.riskLevel === "high"
                          ? "bg-red-500/10 text-red-500"
                          : demo.riskLevel === "medium"
                            ? "bg-amber-500/10 text-amber-500"
                            : "bg-emerald-500/10 text-emerald-500",
                      )}
                    >
                      {demo.riskLevel} risk
                    </span>
                  </div>
                  <p className="line-clamp-2 text-xs text-muted-foreground">{demo.description}</p>
                  <div className="mt-auto flex items-center justify-between pt-1">
                    <span className="text-[10px] text-muted-foreground">
                      {demo.steps.length} {demo.steps.length === 1 ? "step" : "steps"} · {demo.department}
                    </span>
                    <Button
                      asChild
                      variant="ghost"
                      size="sm"
                      className="h-6 gap-1 px-1.5 text-[10px] text-emerald-600 hover:text-emerald-700"
                    >
                      <Link
                        href={`/workflows/new/builder?vendor=${encodeURIComponent(vendor)}&demo=${encodeURIComponent(demo.id)}`}
                      >
                        <Plus className="h-3 w-3" />
                        Install
                      </Link>
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      ) : null}
    </div>
  )
}
