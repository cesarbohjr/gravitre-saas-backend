"use client"

import Link from "next/link"
import { motion } from "framer-motion"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import type { WorkflowFailureAlert } from "@/types/api"

export const FAILURE_SEVERITY_ORDER: WorkflowFailureAlert["severity"][] = [
  "critical",
  "high",
  "medium",
  "low",
]

export const FAILURE_SEVERITY_META: Record<
  WorkflowFailureAlert["severity"],
  { label: string; dot: string; text: string; ring: string }
> = {
  critical: {
    label: "Critical",
    dot: "bg-destructive",
    text: "text-destructive",
    ring: "border-destructive/30 bg-destructive/5",
  },
  high: {
    label: "High",
    dot: "bg-amber-500",
    text: "text-amber-500",
    ring: "border-amber-500/30 bg-amber-500/5",
  },
  medium: {
    label: "Medium",
    dot: "bg-primary",
    text: "text-primary",
    ring: "border-primary/30 bg-primary/5",
  },
  low: {
    label: "Low",
    dot: "bg-muted-foreground",
    text: "text-muted-foreground",
    ring: "border-border bg-card/50",
  },
}

export function groupFailureAlertsBySeverity(alerts: WorkflowFailureAlert[]) {
  return FAILURE_SEVERITY_ORDER.map((severity) => ({
    severity,
    items: alerts.filter((alert) => alert.severity === severity),
  })).filter((group) => group.items.length > 0)
}

export function FailureAlertRow({
  alert,
  onDismiss,
  dismissing,
}: {
  alert: WorkflowFailureAlert
  onDismiss: (id: string) => void
  dismissing: string | null
}) {
  const meta = FAILURE_SEVERITY_META[alert.severity]
  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, x: -16 }}
      transition={{ duration: 0.25 }}
      className={cn("flex gap-3 rounded-lg border p-3", meta.ring)}
    >
      <span className="relative mt-1 flex h-2.5 w-2.5 shrink-0">
        <span className={cn("absolute inline-flex h-full w-full animate-ping rounded-full opacity-60", meta.dot)} />
        <span className={cn("relative inline-flex h-2.5 w-2.5 rounded-full", meta.dot)} />
      </span>
      <div className="min-w-0 flex-1 space-y-1">
        <div className="flex flex-wrap items-center gap-2">
          <p className="text-sm font-medium text-foreground">{alert.title}</p>
          <Badge variant="outline" className={cn("capitalize", meta.text)}>
            {meta.label}
          </Badge>
          {alert.confidence > 0 ? (
            <span className="text-xs tabular-nums text-muted-foreground">
              {Math.round(alert.confidence * 100)}% confidence
            </span>
          ) : null}
        </div>
        <p className="text-xs text-muted-foreground text-pretty">{alert.message}</p>
        <div className="flex flex-wrap items-center gap-2 pt-0.5">
          <Button variant="ghost" size="sm" className="h-7 px-2 text-muted-foreground" asChild>
            <Link href={`/workflows/${alert.workflowId}/builder`}>Open workflow</Link>
          </Button>
          <Button
            variant="ghost"
            size="sm"
            className="h-7 px-2 text-muted-foreground"
            disabled={dismissing === alert.id}
            onClick={() => onDismiss(alert.id)}
          >
            {dismissing === alert.id ? "Dismissing…" : "Dismiss"}
          </Button>
        </div>
      </div>
    </motion.div>
  )
}
