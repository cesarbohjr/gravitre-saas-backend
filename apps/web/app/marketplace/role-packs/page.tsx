"use client"

import { Suspense, useEffect, useMemo, useRef, useState } from "react"
import Link from "next/link"
import { useSearchParams } from "next/navigation"
import useSWR from "swr"
import { motion, AnimatePresence } from "framer-motion"
import { AppShell } from "@/components/gravitre/app-shell"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { GridPattern } from "@/components/gravitre/premium-effects"
import { marketplaceApi } from "@/lib/api"
import { useAuth } from "@/lib/auth-context"
import { cn } from "@/lib/utils"
import {
  ArrowLeft,
  AlertTriangle,
  CheckCircle2,
  Loader2,
  Package,
  Plug,
  Sparkles,
  Bot,
  Workflow,
  Database,
  Lock,
  TrendingUp,
  Headphones,
  Megaphone,
  DollarSign,
  Briefcase,
  PartyPopper,
} from "lucide-react"
import { toast } from "sonner"
import type { DepartmentRolePack, DepartmentRolePackInstallResult } from "@/types/api"

// Department visual theming — accent color + icon per known department.
const DEPARTMENT_THEME: Record<
  string,
  { icon: typeof Briefcase; tint: string; ring: string; text: string; soft: string }
> = {
  sales: {
    icon: TrendingUp,
    tint: "var(--chart-1, var(--primary))",
    ring: "text-primary",
    text: "text-primary",
    soft: "bg-primary/10",
  },
  marketing: {
    icon: Megaphone,
    tint: "var(--chart-2, var(--warning))",
    ring: "text-warning",
    text: "text-warning",
    soft: "bg-warning/10",
  },
  support: {
    icon: Headphones,
    tint: "var(--chart-3, var(--success))",
    ring: "text-success",
    text: "text-success",
    soft: "bg-success/10",
  },
  finance: {
    icon: DollarSign,
    tint: "var(--chart-4, var(--primary))",
    ring: "text-primary",
    text: "text-primary",
    soft: "bg-primary/10",
  },
}

function themeFor(department: string) {
  const key = department.toLowerCase()
  return DEPARTMENT_THEME[key] ?? {
    icon: Briefcase,
    tint: "var(--primary)",
    ring: "text-primary",
    text: "text-primary",
    soft: "bg-primary/10",
  }
}

// Animated circular progress ring showing connector readiness.
function ReadinessRing({
  connected,
  total,
  className,
}: {
  connected: number
  total: number
  className?: string
}) {
  const pct = total === 0 ? 100 : Math.round((connected / total) * 100)
  const radius = 26
  const circumference = 2 * Math.PI * radius
  const ready = pct === 100
  return (
    <div className={cn("relative grid h-16 w-16 place-items-center", className)}>
      <svg className="h-16 w-16 -rotate-90" viewBox="0 0 64 64" aria-hidden>
        <circle
          cx="32"
          cy="32"
          r={radius}
          fill="none"
          strokeWidth="5"
          className="stroke-border"
        />
        <motion.circle
          cx="32"
          cy="32"
          r={radius}
          fill="none"
          strokeWidth="5"
          strokeLinecap="round"
          className={ready ? "stroke-success" : "stroke-primary"}
          strokeDasharray={circumference}
          initial={{ strokeDashoffset: circumference }}
          animate={{ strokeDashoffset: circumference - (pct / 100) * circumference }}
          transition={{ duration: 1, ease: "easeOut" }}
        />
      </svg>
      <div className="absolute inset-0 grid place-items-center">
        {ready ? (
          <CheckCircle2 className="h-6 w-6 text-success" aria-hidden />
        ) : (
          <span className="text-sm font-semibold tabular-nums text-foreground">{pct}%</span>
        )}
      </div>
      <span className="sr-only">
        {connected} of {total} required connectors connected
      </span>
    </div>
  )
}

function ConnectorChecklist({ pack }: { pack: DepartmentRolePack }) {
  return (
    <ul className="space-y-1.5">
      {pack.connectorChecklist.map((item) => (
        <li
          key={`${pack.packId}-${item.connectorType}`}
          className={cn(
            "flex items-center justify-between gap-2 rounded-lg border px-3 py-2 text-sm transition-colors",
            item.connected ? "border-success/30 bg-success/5" : "border-border/60",
          )}
        >
          <div className="flex min-w-0 items-center gap-2">
            <Plug
              className={cn(
                "h-3.5 w-3.5 shrink-0",
                item.connected ? "text-success" : "text-muted-foreground",
              )}
              aria-hidden
            />
            <span className="truncate text-foreground">{item.label}</span>
            {!item.required ? (
              <Badge variant="outline" className="shrink-0 text-[10px]">
                Optional
              </Badge>
            ) : null}
          </div>
          <div className="flex shrink-0 items-center gap-2">
            {item.connected ? (
              <CheckCircle2 className="h-4 w-4 text-success" aria-label="Connected" />
            ) : (
              <Button variant="outline" size="sm" className="h-7" asChild>
                <Link href={item.connectPath || `/connectors?type=${item.connectorType}`}>
                  Connect
                </Link>
              </Button>
            )}
          </div>
        </li>
      ))}
    </ul>
  )
}

function PackContents({ pack }: { pack: DepartmentRolePack }) {
  const items = [
    { icon: Bot, label: "agents", count: pack.agentIds?.length ?? 0 },
    { icon: Workflow, label: "workflows", count: pack.workflowIds?.length ?? 0 },
    { icon: Database, label: "RAG sources", count: pack.ragSourceIds?.length ?? 0 },
  ].filter((i) => i.count > 0)
  if (items.length === 0) return null
  return (
    <div className="flex flex-wrap gap-3">
      {items.map((i) => (
        <div key={i.label} className="flex items-center gap-1.5 text-xs text-muted-foreground">
          <i.icon className="h-3.5 w-3.5" aria-hidden />
          <span className="font-medium text-foreground tabular-nums">{i.count}</span>
          {i.label}
        </div>
      ))}
    </div>
  )
}

function PackCard({
  pack,
  isAdmin,
  installing,
  justInstalled,
  installResult,
  onInstall,
  index,
  highlighted,
}: {
  pack: DepartmentRolePack
  isAdmin: boolean
  installing: string | null
  justInstalled: string | null
  installResult: DepartmentRolePackInstallResult | null
  onInstall: (packId: string) => void
  index: number
  highlighted?: boolean
}) {
  const theme = themeFor(pack.department)
  const DeptIcon = theme.icon
  const ready = pack.connectorsReady || pack.requiredConnectorsTotal === 0
  const blocked = !ready && !pack.installed
  const isInstalling = installing === pack.packId
  const celebrate = justInstalled === pack.packId

  return (
    <motion.div
      id={`role-pack-${pack.packId}`}
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, delay: index * 0.06, ease: "easeOut" }}
      className={cn(
        "group relative flex flex-col overflow-hidden rounded-xl border bg-card transition-shadow hover:shadow-lg",
        pack.installed ? "border-success/30" : "border-border",
        highlighted && "ring-2 ring-primary/50 ring-offset-2 ring-offset-background",
      )}
    >
      {/* Celebration overlay on successful install */}
      <AnimatePresence>
        {celebrate ? (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="pointer-events-none absolute inset-0 z-10 grid place-items-center bg-success/10 backdrop-blur-[1px]"
          >
            <motion.div
              initial={{ scale: 0.6, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              transition={{ type: "spring", stiffness: 260, damping: 16 }}
              className="flex flex-col items-center gap-3 px-4 text-success"
            >
              <PartyPopper className="h-10 w-10" aria-hidden />
              <span className="text-sm font-semibold">Pack installed</span>
              {installResult && justInstalled === pack.packId ? (
                <div className="flex flex-wrap justify-center gap-2">
                  {installResult.agentIds?.[0] ? (
                    <Button size="sm" variant="secondary" asChild>
                      <Link href={`/agents/${installResult.agentIds[0]}`}>Open agent</Link>
                    </Button>
                  ) : null}
                  {installResult.workflowIds?.[0] ? (
                    <Button size="sm" variant="secondary" asChild>
                      <Link href={`/workflows/${installResult.workflowIds[0]}/builder`}>
                        Open workflow
                      </Link>
                    </Button>
                  ) : null}
                  <Button size="sm" variant="outline" asChild>
                    <Link href="/agents">All agents</Link>
                  </Button>
                </div>
              ) : null}
            </motion.div>
          </motion.div>
        ) : null}
      </AnimatePresence>

      <div className={cn("flex items-start gap-3 p-5", theme.soft)}>
        <div className="grid h-11 w-11 shrink-0 place-items-center rounded-lg bg-card shadow-sm">
          <DeptIcon className={cn("h-5 w-5", theme.text)} aria-hidden />
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-start justify-between gap-2">
            <div className="min-w-0">
              <h3 className="truncate font-semibold text-foreground">{pack.name}</h3>
              <p className="text-xs capitalize text-muted-foreground">{pack.department}</p>
            </div>
            {pack.installed ? (
              <Badge
                variant="outline"
                className="shrink-0 border-success/30 bg-success/10 text-success"
              >
                Installed
              </Badge>
            ) : blocked ? (
              <Badge
                variant="outline"
                className="shrink-0 border-warning/30 bg-warning/10 text-warning"
              >
                Setup needed
              </Badge>
            ) : (
              <Badge variant="outline" className="shrink-0">
                Ready
              </Badge>
            )}
          </div>
        </div>
        <ReadinessRing
          connected={pack.requiredConnectorsConnected}
          total={pack.requiredConnectorsTotal}
        />
      </div>

      <div className="flex flex-1 flex-col gap-4 p-5">
        <p className="text-sm text-muted-foreground text-pretty">{pack.description}</p>
        <PackContents pack={pack} />
        <div className="flex flex-wrap gap-1.5">
          {pack.tags.map((tag) => (
            <Badge key={tag} variant="secondary" className="text-[10px] capitalize">
              {tag}
            </Badge>
          ))}
        </div>
        <div>
          <p className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
            Connector checklist · {pack.requiredConnectorsConnected}/{pack.requiredConnectorsTotal}{" "}
            required
          </p>
          <ConnectorChecklist pack={pack} />
        </div>

        <div className="mt-auto pt-1">
          {!isAdmin ? (
            <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
              <Lock className="h-3.5 w-3.5" aria-hidden />
              Admin access required to install
            </p>
          ) : blocked ? (
            <div className="space-y-2">
              <Button className="w-full" disabled variant="outline">
                <Lock className="mr-2 h-4 w-4" aria-hidden />
                Connect required apps to install
              </Button>
              <p className="text-center text-xs text-muted-foreground">
                {pack.requiredConnectorsTotal - pack.requiredConnectorsConnected} required connector
                {pack.requiredConnectorsTotal - pack.requiredConnectorsConnected === 1 ? "" : "s"}{" "}
                still needed
              </p>
            </div>
          ) : (
            <Button
              className="w-full"
              disabled={!!installing}
              onClick={() => onInstall(pack.packId)}
            >
              {isInstalling ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden />
                  Installing…
                </>
              ) : pack.installed ? (
                "Reinstall pack"
              ) : (
                <>
                  <Sparkles className="mr-2 h-4 w-4" aria-hidden />
                  Install pack
                </>
              )}
            </Button>
          )}
        </div>
      </div>
    </motion.div>
  )
}

function RolePacksPageContent() {
  const { user } = useAuth()
  const searchParams = useSearchParams()
  const focusPackId = searchParams.get("pack")
  const [installing, setInstalling] = useState<string | null>(null)
  const [justInstalled, setJustInstalled] = useState<string | null>(null)
  const [lastInstallResult, setLastInstallResult] = useState<DepartmentRolePackInstallResult | null>(null)
  const [filter, setFilter] = useState<string>("all")
  const scrolledToPack = useRef<string | null>(null)
  const role = user?.role
  const isAdmin = role === "admin" || role === "owner"

  const { data, error, isLoading, mutate } = useSWR(
    user ? "marketplace-role-packs" : null,
    () => marketplaceApi.listRolePacks(),
  )

  const handleInstall = async (packId: string) => {
    const packName = (data?.packs ?? []).find((pack) => pack.packId === packId)?.name ?? packId
    setInstalling(packId)
    try {
      const result = await marketplaceApi.installRolePack(packId)
      setLastInstallResult(result)
      toast.success(`${packName} installed`, {
        description: `${result.workflowIds?.length ?? 0} workflow(s), ${result.agentIds?.length ?? 0} agent(s) added`,
        action:
          result.workflowIds?.[0] ? (
            {
              label: "Open workflow",
              onClick: () => {
                window.location.href = `/workflows/${result.workflowIds[0]}/builder`
              },
            }
          ) : undefined,
      })
      setJustInstalled(packId)
      await mutate()
      setTimeout(() => setJustInstalled(null), 4000)
    } catch (err) {
      toast.error("Install failed", {
        description: err instanceof Error ? err.message : "Try again",
      })
    } finally {
      setInstalling(null)
    }
  }

  const packs = data?.packs ?? []
  const departments = useMemo(
    () => Array.from(new Set(packs.map((p) => p.department.toLowerCase()))),
    [packs],
  )
  const visiblePacks = useMemo(
    () => (filter === "all" ? packs : packs.filter((p) => p.department.toLowerCase() === filter)),
    [packs, filter],
  )
  const installedCount = packs.filter((p) => p.installed).length

  useEffect(() => {
    if (!focusPackId || isLoading || packs.length === 0) return
    if (scrolledToPack.current === focusPackId) return
    scrolledToPack.current = focusPackId
    window.setTimeout(() => {
      document.getElementById(`role-pack-${focusPackId}`)?.scrollIntoView({
        behavior: "smooth",
        block: "center",
      })
    }, 150)
  }, [focusPackId, isLoading, packs.length])

  return (
    <AppShell>
      <div className="mx-auto w-full max-w-5xl px-4 py-6 md:px-6 md:py-8">
        {/* Hero header */}
        <div className="relative mb-8 overflow-hidden rounded-2xl border border-border bg-card p-6 md:p-8">
          <GridPattern className="absolute inset-0 opacity-[0.4]" />
          <div className="pointer-events-none absolute -right-12 -top-12 h-48 w-48 rounded-full bg-primary/10 blur-3xl" />
          <div className="relative">
            <Button variant="ghost" size="sm" className="mb-3 -ml-2" asChild>
              <Link href="/connectors">
                <ArrowLeft className="mr-1.5 h-4 w-4" aria-hidden />
                Apps
              </Link>
            </Button>
            <h1 className="flex items-center gap-2.5 text-2xl font-semibold text-foreground md:text-3xl">
              <span className="grid h-10 w-10 place-items-center rounded-xl bg-primary/10">
                <Package className="h-5 w-5 text-primary" aria-hidden />
              </span>
              Department role packs
            </h1>
            <p className="mt-2 max-w-2xl text-sm text-muted-foreground text-pretty md:text-base">
              Stand up an entire department in one click — pre-built agents, RAG sources, workflows,
              and a guided connector checklist for Sales, Marketing, Support, and Finance.
            </p>
            {packs.length > 0 ? (
              <div className="mt-4 flex flex-wrap items-center gap-x-6 gap-y-2 text-sm">
                <span className="text-muted-foreground">
                  <span className="font-semibold text-foreground tabular-nums">{packs.length}</span>{" "}
                  packs available
                </span>
                <span className="text-muted-foreground">
                  <span className="font-semibold text-success tabular-nums">{installedCount}</span>{" "}
                  installed
                </span>
              </div>
            ) : null}
          </div>
        </div>

        {error ? (
          <div
            className="mb-6 flex flex-col gap-3 rounded-lg border border-destructive/30 bg-destructive/5 px-4 py-3 sm:flex-row sm:items-center sm:justify-between"
            role="alert"
          >
            <div className="space-y-1">
              <p className="flex items-center gap-2 text-sm font-medium text-foreground">
                <AlertTriangle className="h-4 w-4 text-destructive" aria-hidden />
                Could not load role packs
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

        {/* Department filter */}
        {departments.length > 1 ? (
          <div className="mb-6 flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => setFilter("all")}
              className={cn(
                "rounded-full border px-3.5 py-1.5 text-sm font-medium capitalize transition-colors",
                filter === "all"
                  ? "border-primary bg-primary text-primary-foreground"
                  : "border-border bg-card text-muted-foreground hover:text-foreground",
              )}
            >
              All departments
            </button>
            {departments.map((dept) => (
              <button
                key={dept}
                type="button"
                onClick={() => setFilter(dept)}
                className={cn(
                  "rounded-full border px-3.5 py-1.5 text-sm font-medium capitalize transition-colors",
                  filter === dept
                    ? "border-primary bg-primary text-primary-foreground"
                    : "border-border bg-card text-muted-foreground hover:text-foreground",
                )}
              >
                {dept}
              </button>
            ))}
          </div>
        ) : null}

        {isLoading && !data ? (
          <div className="grid gap-4 md:grid-cols-2">
            {[0, 1, 2, 3].map((i) => (
              <div
                key={i}
                className="h-80 animate-pulse rounded-xl border border-border bg-muted/40"
              />
            ))}
          </div>
        ) : packs.length === 0 ? (
          <div className="rounded-xl border border-border bg-card py-16 text-center">
            <Package className="mx-auto mb-3 h-10 w-10 text-muted-foreground" aria-hidden />
            <p className="text-sm font-medium text-foreground">No department packs available</p>
            <p className="mt-1 text-sm text-muted-foreground">
              Role packs for this organization will appear here once published.
            </p>
          </div>
        ) : (
          <div className="grid items-start gap-4 md:grid-cols-2">
            {visiblePacks.map((pack, index) => (
              <PackCard
                key={pack.packId}
                pack={pack}
                index={index}
                isAdmin={isAdmin}
                installing={installing}
                justInstalled={justInstalled}
                installResult={lastInstallResult}
                highlighted={focusPackId === pack.packId}
                onInstall={(id) => void handleInstall(id)}
              />
            ))}
          </div>
        )}
      </div>
    </AppShell>
  )
}

function RolePacksPageFallback() {
  return (
    <AppShell>
      <div className="mx-auto w-full max-w-5xl px-4 py-6 md:px-6 md:py-8">
        <div className="grid gap-4 md:grid-cols-2">
          {[0, 1, 2, 3].map((i) => (
            <div
              key={i}
              className="h-80 animate-pulse rounded-xl border border-border bg-muted/40"
            />
          ))}
        </div>
      </div>
    </AppShell>
  )
}

export default function RolePacksPage() {
  return (
    <Suspense fallback={<RolePacksPageFallback />}>
      <RolePacksPageContent />
    </Suspense>
  )
}
