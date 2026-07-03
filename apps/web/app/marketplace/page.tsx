"use client"

import { useMemo, useState } from "react"
import Link from "next/link"
import useSWR from "swr"
import { motion, useReducedMotion } from "framer-motion"
import { AppShell } from "@/components/gravitre/app-shell"
import { Button } from "@/components/ui/button"
import { GridPattern } from "@/components/gravitre/premium-effects"
import { marketplaceApi } from "@/lib/api"
import { useAuth } from "@/lib/auth-context"
import { ROI_PAGE_TITLE } from "@/lib/marketplace-outcome-labels"
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
  Clock,
} from "lucide-react"
import { departmentGradient } from "@/lib/department-gradient"
import { fetcher } from "@/lib/fetcher"
import { roleFromOnboardingStepData, WELCOME_ROLES } from "@/lib/welcome-flow"
import type { OnboardingProgress } from "@/types/api"
import { CategoryIconChip } from "@/components/marketplace/category-icon-chip"
import { PackPreviewSheet } from "@/components/marketplace/pack-preview-sheet"
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

// Hover-reveal pack card. At rest it shows only the catalog orb + name +
// department (a calm, equal grid). On hover/focus the card lifts, gains a 1px
// border in its own department hue, and fades/slides in the description, the
// readiness pill, and a single CTA — the same card revealing more of itself
// (no flip, no front/back swap). The orb is the catalog's CategoryIconChip so
// the icon/color/shape match the browse grid exactly.
function FeaturedPackCard({
  asset,
  index,
  onPreview,
}: {
  asset: MarketplaceAssetSummary
  index: number
  onPreview?: (asset: MarketplaceAssetSummary) => void
}) {
  const reduced = useReducedMotion()
  const { border } = departmentGradient(asset.department)
  const departmentLabel = asset.department ? asset.department.replace(/[-_]/g, " ") : "Department pack"
  const detailHref = `/marketplace/assets/${encodeURIComponent(asset.slug)}`

  return (
    <motion.div
      initial={reduced ? false : { opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, delay: reduced ? 0 : index * 0.05 }}
      className="h-full"
    >
      <div
        className={cn(
          "group/pack relative flex h-full flex-col rounded-2xl border border-border bg-card/60 p-5 text-left",
          "transition-[transform,box-shadow,background-color] duration-200 ease-out",
          "hover:-translate-y-1 hover:bg-card hover:shadow-xl focus-within:ring-2 focus-within:ring-ring",
        )}
      >
        {/* Department-hued border overlay — fades in on hover/focus so a card
            lifts out of the flat resting grid in its own color. */}
        <span
          aria-hidden
          className={cn(
            "pointer-events-none absolute inset-0 rounded-2xl border-2 opacity-0 transition-opacity duration-200 ease-out",
            "group-hover/pack:opacity-100 group-focus-within/pack:opacity-100",
            border,
          )}
        />

        {/* Resting content: orb + name + department label */}
        <div className="flex flex-col items-center text-center">
          <CategoryIconChip assetType="department_pack" department={asset.department} size="lg" />
          <h3 className="mt-4 text-base font-semibold text-foreground text-balance">{asset.title}</h3>
          <p className="mt-0.5 text-xs capitalize text-muted-foreground">{departmentLabel}</p>
        </div>

        {/* Revealed-on-hover content: description, readiness, CTA */}
        <div
          className={cn(
            "grid grid-rows-[0fr] opacity-0 transition-[grid-template-rows,opacity] duration-200 ease-out",
            "group-hover/pack:grid-rows-[1fr] group-hover/pack:opacity-100",
            "group-focus-within/pack:grid-rows-[1fr] group-focus-within/pack:opacity-100",
            reduced && "motion-reduce:transition-none",
          )}
        >
          <div className="overflow-hidden">
            <div className="mt-4 flex flex-col items-center gap-3 text-center">
              <p className="line-clamp-2 text-sm text-muted-foreground text-pretty">{asset.description}</p>
              <ReadinessPill asset={asset} />
              <div className="mt-1 flex flex-wrap items-center justify-center gap-2">
                <Link
                  href={detailHref}
                  className="inline-flex items-center rounded-lg bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground"
                >
                  {asset.installed ? "Manage pack" : "View pack"}
                  <ArrowRight className="ml-1 h-4 w-4" />
                </Link>
                {onPreview ? (
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={() => onPreview(asset)}
                  >
                    Preview
                  </Button>
                ) : null}
              </div>
            </div>
          </div>
        </div>
      </div>
    </motion.div>
  )
}

function MarketplaceHome() {
  const { user } = useAuth()
  const [previewAsset, setPreviewAsset] = useState<MarketplaceAssetSummary | null>(null)
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
  const { data: publisherData } = useSWR(
    user && isAdmin ? "marketplace-publisher-profile-hub" : null,
    () => marketplaceApi.getPublisherProfile(),
  )

  const { data: onboardingProgress } = useSWR<OnboardingProgress>(
    user ? "/api/onboarding" : null,
    fetcher,
    { revalidateOnFocus: false },
  )

  const savedCount = savesData?.total ?? savesData?.saves?.length ?? 0
  const orgPendingCount = orgQueueData?.total ?? 0
  const platformPendingCount = platformQueueData?.total ?? 0
  const orgInternalCount = orgInternalData?.total ?? 0
  const publisherOnboarded = Boolean(publisherData?.publisher?.publicPublishingEnabled)

  const packs = data?.assets ?? []

  // Translate raw backend error codes/messages into friendly, user-facing copy.
  const marketplaceError = (() => {
    const raw = error instanceof Error ? error.message : ""
    const code = raw.trim().toLowerCase()
    if (code.includes("plan_required") || code.includes("plan required")) {
      return {
        title: "Upgrade to access the marketplace",
        description: "Your trial has ended. Choose a plan to browse and install department packs.",
        action: "upgrade" as const,
      }
    }
    return {
      title: "Could not load the marketplace",
      description: "We couldn't reach the marketplace right now. Please try again in a moment.",
      action: "retry" as const,
    }
  })()

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

  const userRole = roleFromOnboardingStepData(onboardingProgress?.step_data)
  const recommendedForYou = useMemo(() => {
    if (packs.length === 0) return []
    const roleConfig = WELCOME_ROLES.find((entry) => entry.id === userRole)
    const roleMatches = roleConfig?.packSlug
      ? packs.filter(
          (pack) =>
            pack.slug === roleConfig.packSlug ||
            pack.department?.toLowerCase().includes(userRole ?? ""),
        )
      : []
    const connectorReady = packs.filter((pack) => !pack.installed && pack.connectorsReady)
    const merged = [...roleMatches]
    for (const pack of connectorReady) {
      if (!merged.some((entry) => entry.id === pack.id)) merged.push(pack)
    }
    return merged.filter((pack) => !pack.installed).slice(0, 6)
  }, [packs, userRole])

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
          description: "Catalog adoption, install activity, and estimated hours saved (ROI).",
          href: "/marketplace/analytics",
          icon: BarChart3,
          show: isAdmin,
        },
        {
          title: ROI_PAGE_TITLE,
          description: "Catalog estimates vs adoption-adopted estimates from installed assets.",
          href: "/marketplace/analytics/roi",
          icon: Clock,
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
          title: publisherOnboarded ? "Publisher profile" : "Become a publisher",
          description: publisherOnboarded
            ? `${publisherData?.publisher?.displayName ?? "Your org"} can submit public catalog assets.`
            : "Onboard your org to submit assets to the public catalog.",
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
    [isAdmin, isPlatformAdmin, orgInternalCount, orgPendingCount, platformPendingCount, publisherData, publisherOnboarded, savedCount],
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
                {marketplaceError.title}
              </p>
              <p className="text-sm text-muted-foreground">{marketplaceError.description}</p>
            </div>
            {marketplaceError.action === "upgrade" ? (
              <Button size="sm" asChild className="shrink-0">
                <Link href="/settings/billing">Upgrade</Link>
              </Button>
            ) : (
              <Button variant="outline" size="sm" onClick={() => void mutate()} className="shrink-0">
                Retry
              </Button>
            )}
          </div>
        ) : null}

        {installedCount === 0 && !isLoading ? (
          <div className="mb-10 rounded-2xl border border-dashed border-primary/30 bg-primary/5 p-8 text-center">
            <div className="mx-auto mb-4 grid h-12 w-12 place-items-center rounded-xl bg-primary/10">
              <Package className="h-6 w-6 text-primary" aria-hidden />
            </div>
            <h2 className="text-lg font-semibold text-foreground">Start building your AI operations team</h2>
            <p className="mx-auto mt-2 max-w-lg text-sm text-muted-foreground text-pretty">
              Install your first department pack to get pre-built agents, workflows, and AI capabilities configured for your team.
            </p>
            <div className="mt-5 flex flex-wrap justify-center gap-3">
              <Button asChild>
                <Link href="/marketplace/assets?type=department_pack">Browse department packs</Link>
              </Button>
              <Button variant="outline" asChild>
                <Link href="/marketplace/assets">Explore all templates</Link>
              </Button>
            </div>
          </div>
        ) : null}

        {recommendedForYou.length > 0 ? (
          <section className="mb-10">
            <div className="mb-4 flex items-end justify-between">
              <div>
                <h2 className="text-lg font-semibold text-foreground">Recommended for you</h2>
                <p className="text-sm text-muted-foreground">
                  Based on your role{userRole ? ` (${WELCOME_ROLES.find((r) => r.id === userRole)?.label ?? userRole})` : ""} and connected apps.
                </p>
              </div>
            </div>
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {recommendedForYou.map((asset, index) => (
                <FeaturedPackCard key={asset.id} asset={asset} index={index} onPreview={setPreviewAsset} />
              ))}
            </div>
          </section>
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
              <p className="text-sm font-medium text-foreground">No department packs available yet</p>
              <p className="mt-1 text-sm text-muted-foreground">
                Check back soon — new ready-to-install packs are added regularly.
              </p>
            </div>
          ) : (
            <div className="grid items-start gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {featured.map((asset, index) => (
                <FeaturedPackCard key={asset.id} asset={asset} index={index} onPreview={setPreviewAsset} />
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

        <PackPreviewSheet
          asset={previewAsset}
          open={Boolean(previewAsset)}
          onOpenChange={(open) => {
            if (!open) setPreviewAsset(null)
          }}
        />
      </div>
    </AppShell>
  )
}

export default function MarketplacePage() {
  return <MarketplaceHome />
}
