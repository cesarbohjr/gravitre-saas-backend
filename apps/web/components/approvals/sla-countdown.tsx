"use client"

import { useEffect, useState } from "react"
import { cn } from "@/lib/utils"
import { Clock, AlertTriangle } from "lucide-react"

function formatRemaining(minutes: number): string {
  if (minutes >= 60) {
    const hours = Math.floor(minutes / 60)
    const mins = Math.round(minutes % 60)
    return mins > 0 ? `${hours}h ${mins}m` : `${hours}h`
  }
  return `${Math.max(0, Math.round(minutes))}m`
}

export function ApprovalSlaCountdown({
  requestedAt,
  slaMinutesRemaining,
  slaBreached,
  className,
}: {
  requestedAt?: string
  slaMinutesRemaining?: number | null
  slaBreached?: boolean
  className?: string
}) {
  const [remaining, setRemaining] = useState(slaMinutesRemaining ?? null)

  useEffect(() => {
    setRemaining(slaMinutesRemaining ?? null)
    if (slaMinutesRemaining == null || slaBreached) return
    const timer = window.setInterval(() => {
      setRemaining((value) => (value == null ? value : Math.max(0, value - 1 / 60)))
    }, 60_000)
    return () => window.clearInterval(timer)
  }, [slaMinutesRemaining, slaBreached, requestedAt])

  if (remaining == null && !slaBreached) return null

  const breached = slaBreached || (remaining != null && remaining <= 0)

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded px-2 py-0.5 text-[10px] font-medium uppercase tabular-nums",
        breached
          ? "bg-destructive/10 text-destructive border border-destructive/20"
          : "bg-amber-500/10 text-amber-600 border border-amber-500/20",
        className,
      )}
    >
      {breached ? (
        <AlertTriangle className="h-3 w-3" aria-hidden />
      ) : (
        <Clock className="h-3 w-3" aria-hidden />
      )}
      {breached ? "SLA breached" : `SLA ${formatRemaining(remaining ?? 0)}`}
    </span>
  )
}
