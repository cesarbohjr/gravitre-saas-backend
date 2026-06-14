"use client"

import { useState } from "react"
import { motion, AnimatePresence } from "framer-motion"
import {
  ArrowUpRight,
  Check,
  X,
  CircleDot,
  CheckCircle2,
  XCircle,
  AlertCircle,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import type { FederationHandoff, FederationHandoffStatus } from "@/types/api"

const STATUS_META: Record<
  FederationHandoffStatus,
  { label: string; icon: typeof CircleDot; tone: string; dot: string }
> = {
  pending_receiver: {
    label: "Pending",
    icon: CircleDot,
    tone: "text-chart-3",
    dot: "bg-chart-3",
  },
  accepted: { label: "Accepted", icon: CheckCircle2, tone: "text-chart-2", dot: "bg-chart-2" },
  completed: { label: "Completed", icon: CheckCircle2, tone: "text-chart-1", dot: "bg-chart-1" },
  rejected: { label: "Declined", icon: XCircle, tone: "text-muted-foreground", dot: "bg-muted-foreground" },
  failed: { label: "Failed", icon: AlertCircle, tone: "text-destructive", dot: "bg-destructive" },
}

function relativeTime(value: string | null) {
  if (!value) return ""
  try {
    const then = new Date(value).getTime()
    const diff = Date.now() - then
    const mins = Math.round(diff / 60000)
    if (mins < 1) return "just now"
    if (mins < 60) return `${mins}m ago`
    const hrs = Math.round(mins / 60)
    if (hrs < 24) return `${hrs}h ago`
    const days = Math.round(hrs / 24)
    return `${days}d ago`
  } catch {
    return ""
  }
}

export function HandoffTimeline({
  handoffs,
  currentOrgId,
  onAction,
}: {
  handoffs: FederationHandoff[]
  currentOrgId?: string
  onAction: (action: "accept" | "reject", handoff: FederationHandoff) => Promise<void>
}) {
  const [busy, setBusy] = useState<string | null>(null)

  async function run(action: "accept" | "reject", handoff: FederationHandoff) {
    setBusy(`${handoff.id}:${action}`)
    try {
      await onAction(action, handoff)
    } finally {
      setBusy(null)
    }
  }

  return (
    <ol className="relative space-y-4 border-l border-border/70 pl-5">
      <AnimatePresence initial={false}>
      {handoffs.map((h, index) => {
        const meta = STATUS_META[h.status]
        const Icon = meta.icon
        const title =
          (typeof h.briefing?.title === "string" && h.briefing.title) ||
          h.message ||
          "Agent handoff"
        const canRespond =
          h.status === "pending_receiver" &&
          Boolean(currentOrgId) &&
          h.receiverOrgId === currentOrgId
        const isPending = h.status === "pending_receiver"

        return (
          <motion.li
            key={h.id}
            layout
            initial={{ opacity: 0, x: -10 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -10 }}
            transition={{ delay: Math.min(index, 6) * 0.05, type: "spring", stiffness: 380, damping: 30 }}
            className="relative"
          >
            <span
              className={cn(
                "absolute -left-[1.6rem] top-1 flex h-3 w-3 items-center justify-center rounded-full ring-4 ring-background",
                meta.dot,
              )}
              aria-hidden
            >
              {isPending && (
                <motion.span
                  className={cn("absolute inset-0 rounded-full", meta.dot)}
                  animate={{ scale: [1, 2.2], opacity: [0.6, 0] }}
                  transition={{ duration: 1.8, repeat: Infinity, ease: "easeOut" }}
                />
              )}
            </span>
            <div className="rounded-lg border border-border bg-card p-3.5">
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium">{title}</p>
                  <p className="mt-0.5 flex items-center gap-1 text-[11px] text-muted-foreground">
                    <span className="inline-flex items-center gap-0.5 font-mono">
                      {h.fromAgentId ? `${h.fromAgentId.slice(0, 6)}` : "org"}
                    </span>
                    <ArrowUpRight className="h-3 w-3" />
                    <span className="inline-flex items-center gap-0.5 font-mono">
                      {h.toAgentId ? `${h.toAgentId.slice(0, 6)}` : "partner"}
                    </span>
                  </p>
                </div>
                <span className={cn("flex shrink-0 items-center gap-1 text-[11px] font-medium", meta.tone)}>
                  <Icon className="h-3 w-3" />
                  {meta.label}
                </span>
              </div>

              <div className="mt-2 flex items-center justify-between gap-2">
                <span className="text-[11px] text-muted-foreground">{relativeTime(h.createdAt)}</span>
                {canRespond && (
                  <div className="flex gap-1.5">
                    <Button
                      size="sm"
                      variant="outline"
                      className="h-7 gap-1 px-2 text-xs"
                      disabled={busy !== null}
                      onClick={() => run("accept", h)}
                    >
                      <Check className="h-3 w-3" />
                      Accept
                    </Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      className="h-7 gap-1 px-2 text-xs text-muted-foreground"
                      disabled={busy !== null}
                      onClick={() => run("reject", h)}
                    >
                      <X className="h-3 w-3" />
                      Decline
                    </Button>
                  </div>
                )}
              </div>
            </div>
          </motion.li>
        )
      })}
      </AnimatePresence>
    </ol>
  )
}
