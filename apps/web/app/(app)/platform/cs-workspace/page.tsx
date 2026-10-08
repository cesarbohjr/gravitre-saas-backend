"use client"

import { useMemo, useState } from "react"
import useSWR from "swr"
import Link from "next/link"
import { formatDistanceToNow } from "date-fns"
import { toast } from "sonner"
import { AppShell } from "@/components/gravitre/app-shell"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { platformApi } from "@/lib/api"
import { useAuth } from "@/lib/auth-context"
import { fetcher } from "@/lib/fetcher"
import { navigateToPlatformOrgView } from "@/lib/org-context"
import { cn } from "@/lib/utils"
import type { PlatformCsAlertItem, PlatformCsTenantSummary } from "@/types/api"
import {
  AlertTriangle,
  ArrowLeft,
  ArrowRight,
  BellOff,
  Building2,
  Camera,
  HeartPulse,
  Loader2,
  Megaphone,
  RefreshCw,
  ShieldAlert,
  UserPlus,
} from "lucide-react"

const GRADE_META: Record<
  string,
  { label: string; badge: string; dot: string }
> = {
  healthy: {
    label: "Healthy",
    badge: "bg-emerald-500/10 text-emerald-600 border-emerald-500/20",
    dot: "bg-emerald-500",
  },
  at_risk: {
    label: "At risk",
    badge: "bg-amber-500/10 text-amber-600 border-amber-500/20",
    dot: "bg-amber-500",
  },
  critical: {
    label: "Critical",
    badge: "bg-destructive/10 text-destructive border-destructive/30",
    dot: "bg-destructive",
  },
}

function formatRelative(iso: string | null | undefined) {
  if (!iso) return "—"
  try {
    return formatDistanceToNow(new Date(iso), { addSuffix: true })
  } catch {
    return iso
  }
}

export default function PlatformCsWorkspacePage() {
  const { user } = useAuth()
  const [gradeFilter, setGradeFilter] = useState<string | null>(null)
  const [hideSnoozed, setHideSnoozed] = useState(false)
  const [needsAttentionOnly, setNeedsAttentionOnly] = useState(false)
  const [backfilling, setBackfilling] = useState(false)

  const { data: me } = useSWR(user ? "/api/auth/me" : null, fetcher)
  const isPlatformAdmin = Boolean((me as { platformAdmin?: boolean } | undefined)?.platformAdmin)

  const swrKey = user && isPlatformAdmin
    ? ["platform-cs-workspace", gradeFilter, hideSnoozed]
    : null

  const { data, error, isLoading, mutate, isValidating } = useSWR(
    swrKey,
    () =>
      platformApi.getCsWorkspaceTenants({
        limit: 50,
        grade: gradeFilter ?? undefined,
        hideSnoozed,
      }),
    { refreshInterval: 60000 },
  )

  const { data: alertsData, mutate: mutateAlerts } = useSWR(
    user && isPlatformAdmin ? "platform-cs-alerts" : null,
    () => platformApi.getCsAlerts({ limit: 20 }),
    { refreshInterval: 60000 },
  )

  const tenants = useMemo(() => {
    const rows = data?.tenants ?? []
    if (!needsAttentionOnly) return rows
    return rows.filter((tenant) => tenant.needsAttention)
  }, [data, needsAttentionOnly])

  const summary = data?.summary

  async function handleBackfill() {
    setBackfilling(true)
    try {
      const result = await platformApi.backfillHealthSnapshots({ limit: 25, lookbackDays: 30 })
      await mutate()
      toast.success(`Backfilled ${result.backfilled} tenant snapshot${result.backfilled === 1 ? "" : "s"}`)
      if (result.errors.length > 0) {
        toast.warning(`${result.errors.length} org(s) failed during backfill`)
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Snapshot backfill failed")
    } finally {
      setBackfilling(false)
    }
  }

  if (!isPlatformAdmin) {
    return (
      <AppShell title="CS Workspace">
        <div className="mx-auto max-w-lg p-8 text-center space-y-4">
          <ShieldAlert className="h-10 w-10 mx-auto text-muted-foreground" />
          <h1 className="text-lg font-semibold">Platform access required</h1>
          <p className="text-sm text-muted-foreground">
            Cross-org CS workspace is limited to Gravitre platform operators.
          </p>
          <Button variant="outline" asChild>
            <Link href="/settings/enterprise?tab=cs">
              <ArrowLeft className="h-4 w-4 mr-2" />
              Org CS dashboard
            </Link>
          </Button>
        </div>
      </AppShell>
    )
  }

  return (
    <AppShell title="CS Workspace">
      <div className="mx-auto max-w-6xl p-4 sm:p-6 space-y-6">
        <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <HeartPulse className="h-5 w-5 text-primary" />
              <h1 className="text-2xl font-semibold tracking-tight">Multi-tenant CS workspace</h1>
            </div>
            <p className="text-sm text-muted-foreground max-w-2xl">
              Cross-org integration health rollups, snapshot backfill, and alert queue actions for Gravitre operators.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            {(summary?.noSnapshot ?? 0) > 0 ? (
              <Button
                variant="secondary"
                size="sm"
                disabled={backfilling}
                onClick={() => void handleBackfill()}
              >
                {backfilling ? (
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                ) : (
                  <Camera className="h-4 w-4 mr-2" />
                )}
                Backfill snapshots ({summary?.noSnapshot})
              </Button>
            ) : null}
            <Button variant="outline" size="sm" onClick={() => void mutate()} disabled={isValidating}>
              <RefreshCw className={cn("h-4 w-4 mr-2", isValidating && "animate-spin")} />
              Refresh
            </Button>
          </div>
        </div>

        {(alertsData?.alerts?.length ?? 0) > 0 ? (
          <AlertInboxPanel alerts={alertsData!.alerts} onRefresh={() => void mutateAlerts()} />
        ) : null}

        {summary ? (
          <div className="grid grid-cols-2 sm:grid-cols-6 gap-3">
            <SummaryTile label="Tenants" value={summary.total} />
            <SummaryTile label="Needs attention" value={summary.needsAttention ?? 0} tone="at_risk" />
            <SummaryTile label="Healthy" value={summary.healthy} tone="healthy" />
            <SummaryTile label="At risk" value={summary.atRisk} tone="at_risk" />
            <SummaryTile label="Critical" value={summary.critical} tone="critical" />
            <SummaryTile label="No snapshot" value={summary.noSnapshot} />
          </div>
        ) : null}

        <div className="flex flex-wrap gap-2">
          {[
            { id: null, label: "All grades" },
            { id: "critical", label: "Critical" },
            { id: "at_risk", label: "At risk" },
            { id: "healthy", label: "Healthy" },
          ].map((filter) => (
            <Button
              key={filter.label}
              size="sm"
              variant={gradeFilter === filter.id ? "default" : "outline"}
              onClick={() => setGradeFilter(filter.id)}
            >
              {filter.label}
            </Button>
          ))}
          <Button
            size="sm"
            variant={needsAttentionOnly ? "default" : "outline"}
            onClick={() => setNeedsAttentionOnly((value) => !value)}
          >
            Needs attention
          </Button>
          <Button
            size="sm"
            variant={hideSnoozed ? "default" : "outline"}
            onClick={() => setHideSnoozed((value) => !value)}
          >
            Hide snoozed
          </Button>
        </div>

        {error ? (
          <Card className="border-destructive/30">
            <CardContent className="pt-6 text-sm text-destructive">
              Failed to load tenant rollups.
            </CardContent>
          </Card>
        ) : isLoading && tenants.length === 0 ? (
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" />
            Loading tenants…
          </div>
        ) : tenants.length === 0 ? (
          <Card>
            <CardContent className="py-10 text-center text-sm text-muted-foreground">
              No tenants match this filter.
            </CardContent>
          </Card>
        ) : (
          <div className="grid gap-3">
            {tenants.map((tenant) => (
              <TenantRow key={tenant.orgId} tenant={tenant} onMutate={() => void mutate()} />
            ))}
          </div>
        )}
      </div>
    </AppShell>
  )
}

function AlertInboxPanel({
  alerts,
  onRefresh,
}: {
  alerts: PlatformCsAlertItem[]
  onRefresh: () => void
}) {
  return (
    <Card className="border-amber-500/25 bg-amber-500/[0.03]">
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between gap-2">
          <CardTitle className="text-base flex items-center gap-2">
            <AlertTriangle className="h-4 w-4 text-amber-600" />
            Cross-org alert inbox
          </CardTitle>
          <Button variant="ghost" size="sm" onClick={onRefresh}>
            Refresh
          </Button>
        </div>
        <CardDescription>Open failure alerts and integration suggestions across tenants.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-2 max-h-64 overflow-auto">
        {alerts.map((alert) => (
          <div
            key={`${alert.kind}-${alert.id}`}
            className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-2 rounded-md border border-border/70 bg-background/60 px-3 py-2 text-sm"
          >
            <div className="min-w-0 space-y-0.5">
              <p className="font-medium truncate">
                {alert.title}{" "}
                <span className="text-muted-foreground font-normal">· {alert.orgName}</span>
              </p>
              {alert.message ? (
                <p className="text-xs text-muted-foreground line-clamp-2">{alert.message}</p>
              ) : null}
            </div>
            <div className="flex items-center gap-2 shrink-0">
              <Badge variant="outline" className="capitalize text-[10px]">
                {alert.kind}
              </Badge>
              {alert.severity ? (
                <Badge variant="outline" className="capitalize text-[10px]">
                  {alert.severity}
                </Badge>
              ) : null}
              <Button
                size="sm"
                variant="outline"
                className="h-7"
                onClick={() =>
                  navigateToPlatformOrgView(
                    { id: alert.orgId, name: alert.orgName },
                    "/settings/enterprise?tab=cs",
                    "/platform/cs-workspace",
                  )
                }
              >
                View
              </Button>
            </div>
          </div>
        ))}
      </CardContent>
    </Card>
  )
}

function SummaryTile({
  label,
  value,
  tone,
}: {
  label: string
  value: number
  tone?: keyof typeof GRADE_META
}) {
  return (
    <div className="rounded-lg border border-border/70 bg-card/50 px-3 py-2">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className={cn("text-xl font-semibold tabular-nums", tone && GRADE_META[tone]?.badge.split(" ")[1])}>
        {value}
      </p>
    </div>
  )
}

function TenantRow({
  tenant,
  onMutate,
}: {
  tenant: PlatformCsTenantSummary
  onMutate: () => void
}) {
  const [busy, setBusy] = useState<string | null>(null)
  const grade = tenant.healthGrade ? GRADE_META[tenant.healthGrade] : null

  function openTenantCsDashboard() {
    navigateToPlatformOrgView(
      { id: tenant.orgId, name: tenant.name },
      "/settings/enterprise?tab=cs",
      "/platform/cs-workspace",
    )
  }

  async function handleAssign() {
    setBusy("assign")
    try {
      await platformApi.assignTenant(tenant.orgId)
      toast.success(`Assigned ${tenant.name} to you`)
      onMutate()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Assign failed")
    } finally {
      setBusy(null)
    }
  }

  async function handleSnooze(hours: number) {
    setBusy(`snooze-${hours}`)
    try {
      await platformApi.snoozeTenant(tenant.orgId, hours)
      toast.success(`Snoozed ${tenant.name} for ${hours}h`)
      onMutate()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Snooze failed")
    } finally {
      setBusy(null)
    }
  }

  async function handleEscalate() {
    setBusy("escalate")
    try {
      const result = await platformApi.escalateTenant(tenant.orgId)
      if (result.delivered) {
        toast.success(`Escalated ${tenant.name} to on-call`)
      } else {
        toast.warning(`Escalation recorded for ${tenant.name}`, {
          description: result.deliveryError ?? "Webhook not configured",
        })
      }
      onMutate()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Escalation failed")
    } finally {
      setBusy(null)
    }
  }

  return (
    <Card
      className={cn(
        "border-border/80",
        tenant.needsAttention && "border-amber-500/30 bg-amber-500/[0.03]",
        tenant.isSnoozed && "opacity-80",
      )}
    >
      <CardHeader className="pb-2">
        <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3">
          <div className="space-y-1 min-w-0">
            <CardTitle className="text-base flex items-center gap-2 flex-wrap">
              <Building2 className="h-4 w-4 text-muted-foreground" />
              {tenant.name}
              {tenant.slug ? (
                <span className="text-xs font-normal text-muted-foreground">/{tenant.slug}</span>
              ) : null}
              {tenant.needsAttention ? (
                <Badge variant="outline" className="border-amber-500/40 text-amber-700">
                  Needs attention
                </Badge>
              ) : null}
              {tenant.isSnoozed ? (
                <Badge variant="outline" className="text-muted-foreground">
                  Snoozed {formatRelative(tenant.snoozedUntil)}
                </Badge>
              ) : null}
            </CardTitle>
            <CardDescription className="font-mono text-xs truncate">{tenant.orgId}</CardDescription>
            {tenant.assignedEmail ? (
              <p className="text-xs text-muted-foreground">Assigned to {tenant.assignedEmail}</p>
            ) : null}
          </div>
          <div className="flex items-center gap-2 flex-wrap">
            {grade ? (
              <Badge variant="outline" className={grade.badge}>
                {grade.label}
              </Badge>
            ) : (
              <Badge variant="outline">No snapshot</Badge>
            )}
            {tenant.healthScore != null ? (
              <Badge variant="secondary">{tenant.healthScore}/100</Badge>
            ) : null}
            <Button
              size="sm"
              variant="outline"
              disabled={busy !== null}
              onClick={() => void handleAssign()}
            >
              {busy === "assign" ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              ) : (
                <>
                  <UserPlus className="h-3.5 w-3.5 mr-1" />
                  Assign
                </>
              )}
            </Button>
            <Button
              size="sm"
              variant="outline"
              disabled={busy !== null || !tenant.needsAttention}
              onClick={() => void handleEscalate()}
            >
              {busy === "escalate" ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              ) : (
                <>
                  <Megaphone className="h-3.5 w-3.5 mr-1" />
                  Escalate
                </>
              )}
            </Button>
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button size="sm" variant="outline" disabled={busy !== null}>
                  {busy?.startsWith("snooze") ? (
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  ) : (
                    <>
                      <BellOff className="h-3.5 w-3.5 mr-1" />
                      Snooze
                    </>
                  )}
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuItem onClick={() => void handleSnooze(24)}>24 hours</DropdownMenuItem>
                <DropdownMenuItem onClick={() => void handleSnooze(72)}>3 days</DropdownMenuItem>
                <DropdownMenuItem onClick={() => void handleSnooze(168)}>7 days</DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
            <Button size="sm" className="gap-1" onClick={openTenantCsDashboard}>
              CS dashboard
              <ArrowRight className="h-3.5 w-3.5" />
            </Button>
          </div>
        </div>
      </CardHeader>
      <CardContent className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-sm">
        <Metric label="Snapshot" value={formatRelative(tenant.healthRecordedAt)} />
        <Metric label="Open suggestions" value={String(tenant.openSuggestions)} />
        <Metric label="Failure alerts" value={String(tenant.activeFailureAlerts)} highlight={tenant.activeFailureAlerts > 0} />
        <Metric label="Health risks" value={String(tenant.riskCount)} highlight={tenant.riskCount > 0} />
      </CardContent>
    </Card>
  )
}

function Metric({
  label,
  value,
  highlight,
}: {
  label: string
  value: string
  highlight?: boolean
}) {
  return (
    <div className="rounded-md border border-border/60 px-3 py-2">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className={cn("font-medium tabular-nums", highlight && "text-amber-600 flex items-center gap-1")}>
        {highlight ? <AlertTriangle className="h-3.5 w-3.5" /> : null}
        {value}
      </p>
    </div>
  )
}
