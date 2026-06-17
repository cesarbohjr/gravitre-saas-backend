"use client"

import { useMemo } from "react"
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
  ArrowRight,
  CheckCircle2,
  TrendingUp,
  Megaphone,
  Headphones,
  DollarSign,
  Briefcase,
  Plug,
  Bot,
  Workflow,
  AlertTriangle,
  Upload,
  Lock,
  ShieldCheck,
} from "lucide-react"
import type { DepartmentRolePack } from "@/types/api"

// Department visual theming — shared with role-packs detail surface.
const DEPARTMENT_THEME: Record<
  string,
  { icon: typeof Briefcase; ring: string; soft: string }
> = {
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

function ReadinessPill({ pack }: { pack: DepartmentRolePack }) {
  if (pack.installed) {
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-success/10 px-2.5 py-1 text-xs font-medium text-success">
        <CheckCircle2 className="h-3.5 w-3.5" aria-hidden />
        Installed
      </span>
    )
  }
  if (pack.connectorsReady) {
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-primary/10 px-2.5 py-1 text-xs font-medium text-primary">
        <Plug className="h-3.5 w-3.5" aria-hidden />
        Ready to install
      </span>
    )
  }
  return (
    <span className="inline-flex items-center gap-1 rounded-full bg-warning/10 px-2.5 py-1 text-xs font-medium text-warning">
      <AlertTriangle className="h-3.5 w-3.5" aria-hidden />
      {pack.requiredConnectorsConnected}/{pack.requiredConnectorsTotal} apps connected
    </span>
  )
}

function FeaturedPackCard({ pack, index }: { pack: DepartmentRolePack; index: number }) {
  const reduced = useReducedMotion()
  const theme = themeFor(pack.department)
  const DeptIcon = theme.icon
  return (
    <motion.div
      initial={reduced ? false : { opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, delay: reduced ? 0 : index * 0.05 }}
    >
      <Link
        href={`/marketplace/role-packs?pack=${encodeURIComponent(pack.packId)}`}
        className="group flex h-full flex-col rounded-xl border border-border bg-card p-5 transition-all hover:border-primary/40 hover:shadow-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        <div className="flex items-start justify-between gap-3">
          <span className={cn("grid h-11 w-11 shrink-0 place-items-center rounded-xl", theme.soft)}>
            <DeptIcon className={cn("h-5 w-5", theme.ring)} aria-hidden />
          </span>
          <ReadinessPill pack={pack} />
        </div>
        <h3 className="mt-4 text-base font-semibold text-foreground">{pack.name}</h3>
        <p className="mt-1.5 line-clamp-2 flex-1 text-sm text-muted-foreground text-pretty">
          {pack.description}
        </p>
        <div className="mt-4 flex flex-wrap items-center gap-x-4 gap-y-1.5 text-xs text-muted-foreground">
          <span className="inline-flex items-center gap-1.5">
            <Bot className="h-3.5 w-3.5" aria-hidden />
            {pack.agentIds?.length ?? 0} agents
          </span>
          <span className="inline-flex items-center gap-1.5">
            <Workflow className="h-3.5 w-3.5" aria-hidden />
            {pack.workflowIds?.length ?? 0} workflows
          </span>
          <span className="inline-flex items-center gap-1.5">
            <Plug className="h-3.5 w-3.5" aria-hidden />
            {pack.requiredConnectorsTotal} apps
          </span>
        </div>
        <span className="mt-4 inline-flex items-center text-sm font-medium text-primary">
          {pack.installed ? "Manage pack" : "View & install"}
          <ArrowRight className="ml-1 h-4 w-4 transition-transform group-hover:translate-x-0.5" aria-hidden />
        </span>
      </Link>
    </motion.div>
  )
}

function MarketplaceHome() {
  const { user } = useAuth()
  const role = user?.role
  const isAdmin = role === "admin" || role === "owner"

  const { data, error, isLoading, mutate } = useSWR(
    user ? "marketplace-role-packs" : null,
    () => marketplaceApi.listRolePacks(),
  )

  const packs = data?.packs ?? []
  const installedCount = packs.filter((p) => p.installed).length
  const readyCount = packs.filter((p) => !p.installed && p.connectorsReady).length
  const departments = useMemo(
    () => Array.from(new Set(packs.map((p) => p.department.toLowerCase()))),
    [packs],
  )

  // Featured = ready-to-install first, then the rest, capped at 6.
  const featured = useMemo(() => {
    return [...packs]
      .sort((a, b) => {
        const aScore = a.installed ? 2 : a.connectorsReady ? 0 : 1
        const bScore = b.installed ? 2 : b.connectorsReady ? 0 : 1
        return aScore - bScore
      })
      .slice(0, 6)
  }, [packs])

  const exploreCards = [
    {
      title: "Department packs",
      description: "Browse every Sales, Marketing, Support, and Finance pack.",
      href: "/marketplace/role-packs",
      icon: Package,
      show: true,
    },
    {
      title: "Installed",
      description: "Manage packs your team has already deployed.",
      href: "/marketplace/installed",
      icon: CheckCircle2,
      show: true,
    },
    {
      title: "Private bundles",
      description: "Upload and activate signed in-house connector bundles.",
      href: "/marketplace/private",
      icon: Lock,
      show: isAdmin,
    },
    {
      title: "Submit a connector",
      description: "Publish a partner connector for security review.",
      href: "/marketplace/submit",
      icon: Upload,
      show: isAdmin,
    },
  ].filter((c) => c.show)

  return (
    <AppShell>
      <div className="mx-auto w-full max-w-5xl px-4 py-6 md:px-6 md:py-8">
        {/* Hero */}
        <div className="relative mb-8 overflow-hidden rounded-2xl border border-border bg-card p-6 md:p-8">
          <GridPattern className="absolute inset-0 opacity-[0.4]" />
          <div className="pointer-events-none absolute -right-12 -top-12 h-48 w-48 rounded-full bg-primary/10 blur-3xl" />
          <div className="relative">
            <h1 className="flex items-center gap-2.5 text-2xl font-semibold text-foreground md:text-3xl">
              <span className="grid h-10 w-10 place-items-center rounded-xl bg-primary/10">
                <Package className="h-5 w-5 text-primary" aria-hidden />
              </span>
              Marketplace
            </h1>
            <p className="mt-2 max-w-2xl text-sm text-muted-foreground text-pretty md:text-base">
              Stand up an entire department in one click — pre-built agents, knowledge sources, and
              workflows with a guided connector checklist. Install an outcome, not just an app.
            </p>
            <div className="mt-5 flex flex-wrap gap-3">
              <Button asChild>
                <Link href="/marketplace/role-packs">
                  Browse department packs
                  <ArrowRight className="ml-1.5 h-4 w-4" aria-hidden />
                </Link>
              </Button>
              {installedCount > 0 ? (
                <Button variant="outline" asChild>
                  <Link href="/marketplace/installed">View installed ({installedCount})</Link>
                </Button>
              ) : null}
            </div>

            {packs.length > 0 ? (
              <div className="mt-6 flex flex-wrap items-center gap-x-8 gap-y-2 text-sm">
                <span className="text-muted-foreground">
                  <span className="font-semibold text-foreground tabular-nums">{packs.length}</span>{" "}
                  packs available
                </span>
                <span className="text-muted-foreground">
                  <span className="font-semibold text-primary tabular-nums">{readyCount}</span> ready
                  to install
                </span>
                <span className="text-muted-foreground">
                  <span className="font-semibold text-success tabular-nums">{installedCount}</span>{" "}
                  installed
                </span>
                <span className="text-muted-foreground">
                  <span className="font-semibold text-foreground tabular-nums">
                    {departments.length}
                  </span>{" "}
                  departments
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
                Could not load the marketplace
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

        {/* Featured packs */}
        <section className="mb-10">
          <div className="mb-4 flex items-end justify-between">
            <div>
              <h2 className="text-lg font-semibold text-foreground">Featured packs</h2>
              <p className="text-sm text-muted-foreground">
                Ready-to-install outcomes based on the apps you&apos;ve connected.
              </p>
            </div>
            <Button variant="ghost" size="sm" asChild className="shrink-0">
              <Link href="/marketplace/role-packs">
                View all
                <ArrowRight className="ml-1 h-4 w-4" aria-hidden />
              </Link>
            </Button>
          </div>

          {isLoading && !data ? (
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {[0, 1, 2, 3, 4, 5].map((i) => (
                <div
                  key={i}
                  className="h-56 animate-pulse rounded-xl border border-border bg-muted/40"
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
            <div className="grid items-start gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {featured.map((pack, index) => (
                <FeaturedPackCard key={pack.packId} pack={pack} index={index} />
              ))}
            </div>
          )}
        </section>

        {/* Explore */}
        <section>
          <h2 className="mb-4 text-lg font-semibold text-foreground">Explore</h2>
          <div className="grid gap-4 sm:grid-cols-2">
            {exploreCards.map((card) => {
              const CardIcon = card.icon
              return (
                <Link
                  key={card.href}
                  href={card.href}
                  className="group flex items-center gap-4 rounded-xl border border-border bg-card p-4 transition-all hover:border-primary/40 hover:shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                >
                  <span className="grid h-10 w-10 shrink-0 place-items-center rounded-lg bg-muted">
                    <CardIcon className="h-5 w-5 text-foreground" aria-hidden />
                  </span>
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-medium text-foreground">{card.title}</p>
                    <p className="truncate text-xs text-muted-foreground">{card.description}</p>
                  </div>
                  <ArrowRight
                    className="h-4 w-4 shrink-0 text-muted-foreground transition-transform group-hover:translate-x-0.5"
                    aria-hidden
                  />
                </Link>
              )
            })}
          </div>
        </section>

        {/* Trust footer */}
        <div className="mt-10 flex items-center justify-center gap-2 text-xs text-muted-foreground">
          <ShieldCheck className="h-3.5 w-3.5" aria-hidden />
          Every published connector passes an automated security review.
        </div>
      </div>
    </AppShell>
  )
}

export default function MarketplacePage() {
  return <MarketplaceHome />
}
