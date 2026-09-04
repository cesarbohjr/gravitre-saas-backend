"use client"

import { useState } from "react"
import Link from "next/link"
import useSWR from "swr"
import { motion, useReducedMotion } from "framer-motion"
import { AppShell } from "@/components/gravitre/app-shell"
import { Button } from "@/components/ui/button"
import { GridPattern } from "@/components/gravitre/premium-effects"
import { marketplaceApi } from "@/lib/api"
import { DepartmentPipelineByDepartment } from "@/components/marketplace/department-pipeline-panel"
import { useAuth } from "@/lib/auth-context"
import { cn } from "@/lib/utils"
import {
  Package,
  ArrowLeft,
  ArrowRight,
  CheckCircle2,
  TrendingUp,
  Megaphone,
  Headphones,
  DollarSign,
  Briefcase,
  Bot,
  Workflow,
  Database,
  AlertTriangle,
  Loader2,
  Trash2,
} from "lucide-react"
import { toast } from "sonner"
import type { MarketplaceInstall } from "@/types/api"

const DEPARTMENT_THEME: Record<string, { icon: typeof Briefcase; ring: string; soft: string }> = {
  sales: { icon: TrendingUp, ring: "text-primary", soft: "bg-primary/10" },
  marketing: { icon: Megaphone, ring: "text-warning", soft: "bg-warning/10" },
  support: { icon: Headphones, ring: "text-success", soft: "bg-success/10" },
  finance: { icon: DollarSign, ring: "text-primary", soft: "bg-primary/10" },
}

function themeFor(department: string) {
  return (
    DEPARTMENT_THEME[department.toLowerCase()] ?? {
      icon: Briefcase,
      ring: "text-primary",
      soft: "bg-primary/10",
    }
  )
}

function formatInstalledAt(value?: string | null) {
  if (!value) return null
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return null
  return date.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" })
}

function InstalledAssetCard({
  install,
  index,
  busy,
  onUninstall,
}: {
  install: MarketplaceInstall
  index: number
  busy: string | null
  onUninstall: (install: MarketplaceInstall) => void
}) {
  const reduced = useReducedMotion()
  const asset = install.asset
  const department = asset?.department ?? "general"
  const theme = themeFor(department)
  const DeptIcon = theme.icon
  const installedAt = formatInstalledAt(install.installedAt)
  const agentCount =
    install.metadata?.agentIds?.length ??
    (install.metadata?.agentId || install.metadata?.operatorId ? 1 : 0)
  const workflowCount =
    install.metadata?.workflowIds?.length ?? (install.metadata?.workflowId ? 1 : 0)
  const sourceCount =
    install.metadata?.ragSourceIds?.length ?? (install.metadata?.ragSourceId ? 1 : 0)
  const slug = asset?.slug
  const deepLinks = (install.deepLinks ?? []).filter(
    (link) => !(link.label === "Primary" && (install.deepLinks?.length ?? 0) > 1),
  )

  return (
    <motion.div
      initial={reduced ? false : { opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, delay: reduced ? 0 : index * 0.05 }}
      className="flex flex-col rounded-3xl border border-border bg-card p-5 shadow-sm"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex min-w-0 items-start gap-3">
          <span className={cn("grid h-11 w-11 shrink-0 place-items-center rounded-2xl", theme.soft)}>
            <DeptIcon className={cn("h-5 w-5", theme.ring)} aria-hidden />
          </span>
          <div className="min-w-0">
            <h3 className="text-base font-semibold tracking-tight text-foreground">
              {asset?.title ?? "Installed asset"}
            </h3>
            <p className="text-xs capitalize text-muted-foreground">{department.replace(/-/g, " ")}</p>
          </div>
        </div>
        <span className="inline-flex shrink-0 items-center gap-1 rounded-full bg-success/10 px-2.5 py-1 text-xs font-medium text-success">
          <CheckCircle2 className="h-3.5 w-3.5" aria-hidden />
          Installed
        </span>
      </div>

      {deepLinks.length ? (
        <div className="mt-4 grid gap-2">
          {deepLinks.slice(0, 4).map((link) => (
            <Link
              key={`${link.entityType}:${link.entityId}:${link.path}`}
              href={link.entityType === "workflow" ? `${link.path}/builder` : link.path}
              className="group flex items-center justify-between rounded-2xl border border-border/70 bg-muted/20 px-3 py-2.5 text-sm transition-colors hover:border-primary/40 hover:bg-muted/40"
            >
              <span className="font-medium text-foreground">{link.label}</span>
              <ArrowRight className="h-4 w-4 text-muted-foreground transition-transform group-hover:translate-x-0.5 group-hover:text-foreground" />
            </Link>
          ))}
        </div>
      ) : (
        <div className="mt-4 grid grid-cols-3 gap-2">
          <Link
            href="/agents"
            className="group rounded-2xl border border-border bg-muted/30 p-2.5 text-center transition-colors hover:border-primary/40"
          >
            <Bot className="mx-auto h-4 w-4 text-muted-foreground group-hover:text-foreground" aria-hidden />
            <p className="mt-1 text-sm font-semibold tabular-nums text-foreground">{agentCount}</p>
            <p className="text-[11px] text-muted-foreground">Agents</p>
          </Link>
          <Link
            href="/workflows"
            className="group rounded-2xl border border-border bg-muted/30 p-2.5 text-center transition-colors hover:border-primary/40"
          >
            <Workflow className="mx-auto h-4 w-4 text-muted-foreground group-hover:text-foreground" aria-hidden />
            <p className="mt-1 text-sm font-semibold tabular-nums text-foreground">{workflowCount}</p>
            <p className="text-[11px] text-muted-foreground">Workflows</p>
          </Link>
          <Link
            href="/sources"
            className="group rounded-2xl border border-border bg-muted/30 p-2.5 text-center transition-colors hover:border-primary/40"
          >
            <Database className="mx-auto h-4 w-4 text-muted-foreground group-hover:text-foreground" aria-hidden />
            <p className="mt-1 text-sm font-semibold tabular-nums text-foreground">{sourceCount}</p>
            <p className="text-[11px] text-muted-foreground">Sources</p>
          </Link>
        </div>
      )}

      <div className="mt-4">
        <DepartmentPipelineByDepartment department={department} />
      </div>

      <div className="mt-4 flex flex-wrap items-center justify-between gap-2 border-t border-border pt-3">
        <span className="text-xs text-muted-foreground">
          {installedAt ? `Installed ${installedAt}` : "Installed"}
        </span>
        <div className="flex items-center gap-1">
          {slug ? (
            <Button variant="ghost" size="sm" className="rounded-full" asChild>
              <Link href={`/marketplace/assets/${encodeURIComponent(slug)}`}>
                Manage
                <ArrowRight className="ml-1 h-4 w-4" aria-hidden />
              </Link>
            </Button>
          ) : null}
          {slug ? (
            <Button
              variant="ghost"
              size="sm"
              className="text-destructive hover:text-destructive"
              disabled={Boolean(busy)}
              onClick={() => onUninstall(install)}
            >
              {busy === install.id ? (
                <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" aria-hidden />
              ) : (
                <Trash2 className="mr-1.5 h-3.5 w-3.5" aria-hidden />
              )}
              Uninstall
            </Button>
          ) : null}
        </div>
      </div>
    </motion.div>
  )
}

function InstalledContent() {
  const { user } = useAuth()
  const [busy, setBusy] = useState<string | null>(null)
  const { data, error, isLoading, mutate } = useSWR(
    user ? "marketplace-installs" : null,
    () => marketplaceApi.listInstalls({ status: "active", limit: 100 }),
  )

  const installed = data?.installs ?? []

  const handleUninstall = async (install: MarketplaceInstall) => {
    const slug = install.asset?.slug
    if (!slug) return
    if (!window.confirm(`Uninstall "${install.asset?.title ?? slug}"? This removes the marketplace install record.`)) {
      return
    }
    setBusy(install.id)
    try {
      await marketplaceApi.uninstallAsset(slug)
      toast.success("Asset uninstalled")
      await mutate()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Uninstall failed")
    } finally {
      setBusy(null)
    }
  }

  return (
    <AppShell>
      <div className="mx-auto w-full max-w-5xl px-4 py-6 md:px-6 md:py-8">
        <div className="mb-8">
          <Button variant="ghost" size="sm" className="mb-3 -ml-2" asChild>
            <Link href="/marketplace/assets">
              <ArrowLeft className="mr-1.5 h-4 w-4" aria-hidden />
              Marketplace
            </Link>
          </Button>
          <h1 className="flex items-center gap-2.5 text-2xl font-semibold text-foreground md:text-3xl">
            <span className="grid h-10 w-10 place-items-center rounded-xl bg-success/10">
              <CheckCircle2 className="h-5 w-5 text-success" aria-hidden />
            </span>
            Installed assets
          </h1>
          <p className="mt-2 max-w-2xl text-sm text-muted-foreground text-pretty md:text-base">
            Marketplace assets your team has deployed, with quick links to agents, workflows, and knowledge sources.
          </p>
        </div>

        {error ? (
          <div
            className="mb-6 flex flex-col gap-3 rounded-lg border border-destructive/30 bg-destructive/5 px-4 py-3 sm:flex-row sm:items-center sm:justify-between"
            role="alert"
          >
            <div className="space-y-1">
              <p className="flex items-center gap-2 text-sm font-medium text-foreground">
                <AlertTriangle className="h-4 w-4 text-destructive" aria-hidden />
                Could not load installed assets
              </p>
              <p className="text-sm text-muted-foreground">
                {error instanceof Error ? error.message : "Check backend connectivity and try again."}
              </p>
            </div>
            <Button variant="outline" size="sm" onClick={() => void mutate()}>
              Retry
            </Button>
          </div>
        ) : null}

        {isLoading && !data ? (
          <div className="grid gap-4 sm:grid-cols-2">
            {[0, 1, 2, 3].map((i) => (
              <div key={i} className="h-64 animate-pulse rounded-xl border border-border bg-muted/40" />
            ))}
          </div>
        ) : installed.length === 0 ? (
          <div className="relative overflow-hidden rounded-2xl border border-border bg-card py-16 text-center">
            <GridPattern className="absolute inset-0 opacity-[0.3]" />
            <div className="relative">
              <span className="mx-auto mb-4 grid h-14 w-14 place-items-center rounded-2xl bg-primary/10">
                <Package className="h-7 w-7 text-primary" aria-hidden />
              </span>
              <p className="text-base font-medium text-foreground">Nothing installed yet</p>
              <p className="mx-auto mt-1.5 max-w-md text-sm text-muted-foreground text-pretty">
                Install a department pack or catalog asset to deploy agents, workflows, and knowledge in one click.
              </p>
              <Button asChild className="mt-5">
                <Link href="/marketplace/assets?type=department_pack">
                  Browse department packs
                  <ArrowRight className="ml-1.5 h-4 w-4" aria-hidden />
                </Link>
              </Button>
            </div>
          </div>
        ) : (
          <div className="grid items-start gap-4 sm:grid-cols-2">
            {installed.map((install, index) => (
              <InstalledAssetCard
                key={install.id}
                install={install}
                index={index}
                busy={busy}
                onUninstall={handleUninstall}
              />
            ))}
          </div>
        )}
      </div>
    </AppShell>
  )
}

export default function InstalledPage() {
  return <InstalledContent />
}
