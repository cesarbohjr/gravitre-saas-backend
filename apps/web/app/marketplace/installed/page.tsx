"use client"

import Link from "next/link"
import useSWR from "swr"
import { motion, useReducedMotion } from "framer-motion"
import { AppShell } from "@/components/gravitre/app-shell"
import { Button } from "@/components/ui/button"
import { GridPattern } from "@/components/gravitre/premium-effects"
import { marketplaceApi } from "@/lib/api"
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
} from "lucide-react"
import type { DepartmentRolePack } from "@/types/api"

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

function InstalledPackCard({ pack, index }: { pack: DepartmentRolePack; index: number }) {
  const reduced = useReducedMotion()
  const theme = themeFor(pack.department)
  const DeptIcon = theme.icon
  const installedAt = formatInstalledAt(pack.installedAt)
  const agentCount = pack.agentIds?.length ?? 0
  const workflowCount = pack.workflowIds?.length ?? 0
  const sourceCount = pack.ragSourceIds?.length ?? 0

  return (
    <motion.div
      initial={reduced ? false : { opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, delay: reduced ? 0 : index * 0.05 }}
      className="flex flex-col rounded-xl border border-border bg-card p-5"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex min-w-0 items-start gap-3">
          <span className={cn("grid h-11 w-11 shrink-0 place-items-center rounded-xl", theme.soft)}>
            <DeptIcon className={cn("h-5 w-5", theme.ring)} aria-hidden />
          </span>
          <div className="min-w-0">
            <h3 className="text-base font-semibold text-foreground">{pack.name}</h3>
            <p className="text-xs capitalize text-muted-foreground">{pack.department}</p>
          </div>
        </div>
        <span className="inline-flex shrink-0 items-center gap-1 rounded-full bg-success/10 px-2.5 py-1 text-xs font-medium text-success">
          <CheckCircle2 className="h-3.5 w-3.5" aria-hidden />
          Installed
        </span>
      </div>

      <p className="mt-3 line-clamp-2 text-sm text-muted-foreground text-pretty">
        {pack.description}
      </p>

      {/* What this pack deployed */}
      <div className="mt-4 grid grid-cols-3 gap-2">
        <Link
          href="/agents"
          className="group rounded-lg border border-border bg-muted/30 p-2.5 text-center transition-colors hover:border-primary/40"
        >
          <Bot className="mx-auto h-4 w-4 text-muted-foreground group-hover:text-foreground" aria-hidden />
          <p className="mt-1 text-sm font-semibold tabular-nums text-foreground">{agentCount}</p>
          <p className="text-[11px] text-muted-foreground">Agents</p>
        </Link>
        <Link
          href="/workflows"
          className="group rounded-lg border border-border bg-muted/30 p-2.5 text-center transition-colors hover:border-primary/40"
        >
          <Workflow className="mx-auto h-4 w-4 text-muted-foreground group-hover:text-foreground" aria-hidden />
          <p className="mt-1 text-sm font-semibold tabular-nums text-foreground">{workflowCount}</p>
          <p className="text-[11px] text-muted-foreground">Workflows</p>
        </Link>
        <Link
          href="/sources"
          className="group rounded-lg border border-border bg-muted/30 p-2.5 text-center transition-colors hover:border-primary/40"
        >
          <Database className="mx-auto h-4 w-4 text-muted-foreground group-hover:text-foreground" aria-hidden />
          <p className="mt-1 text-sm font-semibold tabular-nums text-foreground">{sourceCount}</p>
          <p className="text-[11px] text-muted-foreground">Sources</p>
        </Link>
      </div>

      <div className="mt-4 flex items-center justify-between border-t border-border pt-3">
        <span className="text-xs text-muted-foreground">
          {installedAt ? `Installed ${installedAt}` : "Installed"}
        </span>
        <Button variant="ghost" size="sm" asChild className="-mr-2">
          <Link href={`/marketplace/role-packs?pack=${encodeURIComponent(pack.packId)}`}>
            Manage
            <ArrowRight className="ml-1 h-4 w-4" aria-hidden />
          </Link>
        </Button>
      </div>
    </motion.div>
  )
}

function InstalledContent() {
  const { user } = useAuth()
  const { data, error, isLoading, mutate } = useSWR(
    user ? "marketplace-role-packs" : null,
    () => marketplaceApi.listRolePacks(),
  )

  const installed = (data?.packs ?? []).filter((p) => p.installed)

  return (
    <AppShell>
      <div className="mx-auto w-full max-w-5xl px-4 py-6 md:px-6 md:py-8">
        {/* Header */}
        <div className="mb-8">
          <Button variant="ghost" size="sm" className="mb-3 -ml-2" asChild>
            <Link href="/marketplace">
              <ArrowLeft className="mr-1.5 h-4 w-4" aria-hidden />
              Marketplace
            </Link>
          </Button>
          <h1 className="flex items-center gap-2.5 text-2xl font-semibold text-foreground md:text-3xl">
            <span className="grid h-10 w-10 place-items-center rounded-xl bg-success/10">
              <CheckCircle2 className="h-5 w-5 text-success" aria-hidden />
            </span>
            Installed packs
          </h1>
          <p className="mt-2 max-w-2xl text-sm text-muted-foreground text-pretty md:text-base">
            Department packs your team has deployed, with quick links to the agents, workflows, and
            knowledge sources they created.
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
                Could not load installed packs
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
              <p className="text-base font-medium text-foreground">No packs installed yet</p>
              <p className="mx-auto mt-1.5 max-w-md text-sm text-muted-foreground text-pretty">
                Install a department pack to deploy a full set of agents, workflows, and knowledge
                sources in one click.
              </p>
              <Button asChild className="mt-5">
                <Link href="/marketplace/role-packs">
                  Browse department packs
                  <ArrowRight className="ml-1.5 h-4 w-4" aria-hidden />
                </Link>
              </Button>
            </div>
          </div>
        ) : (
          <div className="grid items-start gap-4 sm:grid-cols-2">
            {installed.map((pack, index) => (
              <InstalledPackCard key={pack.packId} pack={pack} index={index} />
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
