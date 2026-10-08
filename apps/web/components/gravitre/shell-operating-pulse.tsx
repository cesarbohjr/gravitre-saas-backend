"use client"

import Link from "next/link"
import useSWR from "swr"
import { cn } from "@/lib/utils"
import { useAuth } from "@/lib/auth-context"
import { APP_ROUTES } from "@/lib/app-routes"
import { ASSIGNMENTS_REFRESH_KEY, fetchAssignmentList } from "@/lib/assignments-list"
import type { DemoAssignment } from "@/lib/demo-assignments"

type PulseSegment = {
  id: string
  label: string
  href: string
  tone: "live" | "attention" | "fault" | "quiet"
  /** Lower-priority segments only appear on the widest screens. */
  wideOnly?: boolean
}

/**
 * Live operating state carried by the shell on every page. Segments render only
 * from loaded counts; a segment with no data is omitted rather than shown as 0.
 */
export function ShellOperatingPulse({
  pendingApprovals,
  activeWorkflows,
  className,
}: {
  pendingApprovals: number | null
  activeWorkflows: number | null
  className?: string
}) {
  const { user } = useAuth()
  const { data: assignments } = useSWR<DemoAssignment[]>(
    user ? ASSIGNMENTS_REFRESH_KEY : null,
    fetchAssignmentList,
    { revalidateOnFocus: false, refreshInterval: 60_000 },
  )

  const running = assignments ? assignments.filter((a) => a.status === "running").length : null
  const failed = assignments ? assignments.filter((a) => a.status === "failed").length : null

  const segments: PulseSegment[] = []
  if (running !== null) {
    segments.push({
      id: "running",
      label: `${running} running`,
      href: "/assignments",
      tone: running > 0 ? "live" : "quiet",
    })
  }
  if (pendingApprovals !== null) {
    segments.push({
      id: "approvals",
      label: `${pendingApprovals} need you`,
      href: APP_ROUTES.approvals,
      tone: pendingApprovals > 0 ? "attention" : "quiet",
    })
  }
  if (failed) {
    segments.push({ id: "failed", label: `${failed} failed`, href: "/assignments", tone: "fault" })
  }
  if (activeWorkflows !== null) {
    segments.push({
      id: "workflows",
      label: `${activeWorkflows} workflow${activeWorkflows === 1 ? "" : "s"} live`,
      href: APP_ROUTES.workflows,
      tone: "quiet",
      wideOnly: true,
    })
  }

  if (segments.length === 0) return null

  return (
    <nav
      aria-label="Operating state"
      data-testid="shell-operating-pulse"
      className={cn("items-center gap-px rounded-[4px] border border-[color:var(--g-frame-rule)] p-0.5", className)}
    >
      {segments.map((segment) => (
        <Link
          key={segment.id}
          href={segment.href}
          data-pulse={segment.id}
          className={cn(
            "h-6 items-center gap-1.5 rounded-[2px] px-2 text-xs font-medium tabular-nums text-muted-foreground transition-colors hover:bg-foreground/[0.08] hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
            segment.wideOnly ? "hidden 2xl:inline-flex" : "inline-flex",
          )}
        >
          <span
            aria-hidden
            className={cn(
              "size-1.5 rounded-full",
              segment.tone === "live" && "bg-[color:var(--g-brand)]",
              segment.tone === "attention" && "bg-warning",
              segment.tone === "fault" && "bg-destructive",
              segment.tone === "quiet" && "bg-muted-foreground/40",
            )}
          />
          <span className={cn(segment.tone !== "quiet" && "text-foreground")}>{segment.label}</span>
        </Link>
      ))}
    </nav>
  )
}
