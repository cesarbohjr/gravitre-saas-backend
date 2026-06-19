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
  Plug,
  AlertTriangle,
  Upload,
  Lock,
  ShieldCheck,
  Sparkles,
  Briefcase,
  BarChart3,
  Building2,
  Shield,
  Globe,
  HeartPulse,
  TrendingUp,
  Bookmark,
} from "lucide-react"
import { departmentTheme } from "@/lib/department-theme"
import { fetcher } from "@/lib/fetcher"
import { FlipPackCard } from "@/components/marketplace/flip-pack-card"
import { PackFrontArt } from "@/components/marketplace/pack-front-art"
import type { MarketplaceAssetSummary } from "@/types/api"

function ReadinessPill({ asset }: { asset: MarketplaceAssetSummary }) {
  if (asset.installed) {
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-success/10 px-2.5 py-1 text-xs font-medium text-success">
        <CheckCircle2 className="h-3.5 w-3.5" aria-hidden />
        Installed
      </span>
    )
  }
  if (asset.connectorsReady) {
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
      {asset.requiredConnectorsConnected}/{asset.requiredConnectorsTotal} apps connected
    </span>
  )
}

// Back face of the flip card — the detailed pack info, matching the unified
// asset model. The card surface (border/bg/rounded) is provided by the flip
// face shell; this owns the inner padding, layout, and the "View & install" CTA.
function FeaturedPackCardBack({ asset }: { asset: MarketplaceAssetSummary }) {
  const theme = departmentTheme(asset.department)
  const DeptIcon = theme.icon
  return (
    <div className="flex h-full flex-col p-5">
      <div className="flex items-start justify-between gap-3">
        <span className={cn("grid h-11 w-11 shrink-0 place-items-center rounded-xl", theme.soft)}>
          <DeptIcon className={cn("h-5 w-5", theme.ring)} aria-hidden />
        </span>
        <ReadinessPill asset={asset} />
      </div>
      <div className="mt-4 flex flex-wrap items-center gap-2">
        <h3 className="text-base font-semibold text-foreground">{asset.title}</h3>
        {asset.verified ? (
          <span className="inline-flex items-center gap-1 rounded-full bg-primary/10 px-2 py-0.5 text-[11px] font-medium text-primary">
            <ShieldCheck className="h-3 w-3" aria-hidden />
            Verified
          </span>
        ) : null}
      </div>
      <p className="mt-1.5 line-clamp-2 flex-1 text-sm text-muted-foreground text-pretty">
        {asset.description}
      </p>
      <div className="mt-4 flex flex-wrap items-center gap-x-4 gap-y-1.5 text-xs text-muted-foreground">
        {asset.department ? (
          <span className="capitalize">{asset.department.replace(/-/g, " ")}</span>
        ) : null}
        <span className="inline-flex items-center gap-1.5">
          <Plug className="h-3.5 w-3.5" aria-hidden />
          {asset.requiredConnectorsTotal} apps
        </span>
        {(asset.installCount ?? 0) > 0 ? (
          <span className="inline-flex items-center gap-1.5">
            <Sparkles className="h-3.5 w-3.5" aria-hidden />
            {asset.installCount} installs
          </span>
        ) : null}
      </div>
      {/* stopPropagation so clicking the CTA navigates instead of re-toggling
          the card's flip handler. */}
      <Link
        href={`/marketplace/assets/${encodeURIComponent(asset.slug)}`}
        onClick={(e) => e.stopPropagation()}
        className="group/cta mt-4 inline-flex w-fit items-center rounded text-sm font-medium text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        {asset.installed ? "Manage pack" : "View & install"}
        <ArrowRight
          className="ml-1 h-4 w-4 transition-transform group-hover/cta:translate-x-0.5"
          aria-hidden
        />
      </Link>
    </div>
  )
}

function FeaturedPackCard({ asset, index }: { asset: MarketplaceAssetSummary; index: number }) {
  const reduced = useReducedMotion()
  return (
    <motion.div
      initial={reduced ? false : { opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, delay: reduced ? 0 : index * 0.05 }}
    >
      <FlipPackCard
        packId={asset.slug}
        frontContent={<PackFrontArt department={asset.department} packName={asset.title} />}
        backContent={<FeaturedPackCardBack asset={asset} />}
      />
    </motion.div>
  )
}

function MarketplaceHome() {
  const { user } = useAuth()
  const role = user?.role
  const isAdmin = role === "admin" || role === "owner"
  const { data: me } = useSWR(user ? "/api/auth/me" : null, fetcher)
  const isPlatformAdmin = Boolean((me as { platformAdmin?: boolean } | undefined)?.platformAdmin)

  const { data, error, isLoading, mutate } = useSWR(
    user ? "marketplace-department-packs" : null,
    () => marketplaceApi.listAssets({ assetType: "department_pack", limit: 50 }),
  )
  const { data: featuredData } = useSWR(user ? "marketplace-featured" : null, () =>
    marketplaceApi.listAssets({ featured: true, limit: 6 }),
  )
  const { data: categories } = useSWR(user ? "marketplace-categories" : null, () =>
    marketplaceApi.listCategories(),
  )
  const { data: savesData } = useSWR(user ? "marketplace-saves" : null, () =>
    marketplaceApi.listSaves({ limit: 100 }),
  )
  const { data: orgQueueData } = useSWR(
    user && isAdmin ? "marketplace-org-queue-count" : null,
    () => marketplaceApi.listOrgAssets({ status: "pending_review", limit: 1 }),
  )
  const { data: platformQueueData } = useSWR(
    user && isPlatformAdmin ? "marketplace-platform-queue-count" : null,
    () => marketplaceApi.listPlatformReviewQueue({ limit: 1 }),
  )
  const { data: orgInternalData } = useSWR(user ? "marketplace-org-internal-count" : null, () =>
    marketplaceApi.listAssets({ visibility: "internal", limit: 1 }),
  )

  const savedCount = savesData?.total ?? savesData?.saves?.length ?? 0
  const orgPendingCount = orgQueueData?.total ?? 0
  const platformPendingCount = platformQueueData?.total ?? 0
  const orgInternalCount = orgInternalData?.total ?? 0

  const packs = data?.assets ?? []
  const installedCount = packs.filter((p) => p.installed).length
  const readyCount = packs.filter((p) => !p.installed && p.connectorsReady).length
  const departments = categories?.departments ?? []

  const featured = useMemo(() => {
    const curated = featuredData?.assets ?? []
    if (curated.length > 0) return curated
    return [...packs]
      .sort((a, b) => {
        const aScore = a.installed ? 2 : a.connectorsReady ? 0 : 1
        const bScore = b.installed ? 2 : b.connectorsReady ? 0 : 1
        return aScore - bScore
      })
      .slice(0, 6)
  }, [featuredData?.assets, packs])

  const exploreCards = useMemo(
    () =>
      [
        {
          title: "Browse catalog",
          description: "Agents, workflows, knowledge packs, and department outcomes.",
          href: "/marketplace/assets",
          icon: Package,
          show: true,
        },
        {
          title: savedCount > 0 ? `Saved (${savedCount})` : "Saved assets",
          description: "Bookmarked catalog items and community signals.",
          href: "/marketplace/saved",
          icon: Bookmark,
          show: true,
        },
        {
          title: "Partner connectors",
          description: "Federated partner registry in unified catalog shape.",
          href: "/marketplace/connectors",
          icon: Plug,
          show: true,
        },
        {
          title: "Analytics",
          description: "Catalog adoption and your org install activity.",
          href: "/marketplace/analytics",
          icon: BarChart3,
          show: isAdmin,
        },
        {
          title: "Department packs",
          description: "Sales, Marketing, Support, Finance, and HR department outcomes.",
          href: "/marketplace/assets?type=department_pack",
          icon: Briefcase,
          show: true,
        },
        {
          title: orgInternalCount > 0 ? `Your organization (${orgInternalCount})` : "Your organization",
          description: "Internal assets shared only within your org.",
          href: "/marketplace/org",
          icon: Building2,
          show: true,
        },
        {
          title: orgPendingCount > 0 ? `Publish queue (${orgPendingCount})` : "Publish queue",
          description: "Review org-owned drafts before internal publish.",
          href: "/marketplace/org-admin",
          icon: Shield,
          show: isAdmin,
        },
        {
          title: "Become a publisher",
          description: "Onboard your org to submit assets to the public catalog.",
          href: "/marketplace/publisher",
          icon: Sparkles,
          show: isAdmin,
        },
        {
          title: "Publisher revenue",
          description: "Earnings from connector usage and paid asset sales.",
          href: "/marketplace/publisher/analytics",
          icon: TrendingUp,
          show: isAdmin,
        },
        {
          title:
            platformPendingCount > 0
              ? `Public review (${platformPendingCount})`
              : "Public review",
          description: "Gravitre platform queue for community submissions.",
          href: "/marketplace/platform-admin",
          icon: Globe,
          show: isPlatformAdmin,
        },
        {
          title: "CS workspace",
          description: "Cross-org tenant health rollups and alert queues.",
          href: "/platform/cs-workspace",
          icon: HeartPulse,
          show: isPlatformAdmin,
        },
        {
          title: "Installed",
          description: "Manage assets your team has already deployed.",
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
      ].filter((c) => c.show),
    [isAdmin, isPlatformAdmin, orgInternalCount, orgPendingCount, platformPendingCount, savedCount],
  )

  return (
    <AppShell>
      <div className="mx-auto w-full max-w-5xl px-4 py-6 md:px-6 md:py-8">
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
                <Link href="/marketplace/assets">
                  Browse catalog
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
                  department packs
                </span>
                <span className="text-muted-foreground">
                  <span className="font-semibold text-primary tabular-nums">{readyCount}</span> ready
                  to install
                </span>
                <span className="text-muted-foreground">
                  <span className="font-semibold text-success tabular-nums">{installedCount}</span>{" "}
                  installed
                </span>
                {categories ? (
                  <span className="text-muted-foreground">
                    <span className="font-semibold text-foreground tabular-nums">
                      {categories.totalAssets}
                    </span>{" "}
                    total assets
                  </span>
                ) : null}
                {departments.length > 0 ? (
                  <span className="text-muted-foreground">
                    <span className="font-semibold text-foreground tabular-nums">
                      {departments.length}
                    </span>{" "}
                    departments
                  </span>
                ) : null}
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

        <section className="mb-10">
          <div className="mb-4 flex items-end justify-between">
            <div>
              <h2 className="text-lg font-semibold text-foreground">Featured packs</h2>
              <p className="text-sm text-muted-foreground">
                Ready-to-install outcomes based on the apps you&apos;ve connected.
              </p>
            </div>
            <Button variant="ghost" size="sm" asChild className="shrink-0">
              <Link href="/marketplace/assets?type=department_pack">
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
                Run backend/scripts/seed_marketplace.py after applying marketplace migrations.
              </p>
            </div>
          ) : (
            <div className="grid items-start gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {featured.map((asset, index) => (
                <FeaturedPackCard key={asset.id} asset={asset} index={index} />
              ))}
            </div>
          )}
        </section>

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
