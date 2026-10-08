"use client"

import { Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react"
import Link from "next/link"
import { useParams, useRouter, useSearchParams } from "next/navigation"
import useSWR from "swr"
import { MarketplaceDecisionDialog } from "@/components/marketplace/marketplace-decision-dialog"
import { WorkSectionErrorCard } from "@/components/gravitre/work-section-error-card"
import { AppShell } from "@/components/gravitre/app-shell"
import { WsPage } from "@/components/workspace/ws-page"
import { ProviderLogo } from "@/components/gravitre/provider-logo"
import { AssetReviewsSection } from "@/components/marketplace/asset-reviews-section"
import { InstallStepperSheet } from "@/components/marketplace/install-experience"
import {
  NonAdminPurchaseNotice,
  PackContentsPreview,
  assetRequiresPurchase,
  formatAssetPrice,
} from "@/components/marketplace/marketplace-asset-commerce"
import { Button } from "@/components/ui/button"
import { departmentPipelinesApi, marketplaceApi } from "@/lib/api"
import { useAuth } from "@/lib/auth-context"
import { useOrgAdmin } from "@/lib/use-org-admin"
import { pipelineDepartmentKey } from "@/lib/marketplace-department-pipeline"
import { resolveMarketArt } from "@/lib/marketplace-category-art"
import { ESTIMATED_HOURS_SAVED_MONTHLY } from "@/lib/outcome-labels"
import {
  approvalGateCount,
  departmentLabel,
  isReportOutput,
  marketplaceTypeLabel,
  pipelineFitStages,
  requiredAppsLabel,
  templateCadence,
  templateOutput,
  templateSteps,
  type TemplateOutput,
  type TemplateStep,
} from "@/lib/marketplace-template-detail"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import {
  AlertCircle,
  Check,
  CheckCircle2,
  Copy,
  Loader2,
  MoreHorizontal,
  ShieldCheck,
  ShoppingCart,
  Trash2,
} from "lucide-react"
import { toast } from "sonner"
import type {
  MarketplaceAssetDetail,
  MarketplaceAssetSummary,
  MarketplaceConnectorChecklistItem,
  MarketplaceInstallBlocker,
} from "@/types/api"
import "./template-detail.css"

/** "google_analytics" -> "Google Analytics" for the connect link. */
function connectorLabel(key: string): string {
  return key
    .split(/[_\-\s]+/)
    .filter(Boolean)
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ")
}

function BlockerList({ blockers }: { blockers: MarketplaceInstallBlocker[] }) {
  if (!blockers.length) return null
  return (
    <ul className="space-y-2 rounded-2xl border border-destructive/30 bg-destructive/5 p-3 text-sm">
      {blockers.map((blocker) => (
        <li key={blocker.connector} className="flex items-start gap-2">
          <AlertCircle
            className="mt-0.5 h-4 w-4 shrink-0 text-destructive"
            aria-hidden
          />
          <div className="flex-1">
            <p>{blocker.reason}</p>
            {blocker.action_url ? (
              <Link
                href={blocker.action_url}
                className="text-primary underline-offset-4 hover:underline"
              >
                Connect {connectorLabel(blocker.connector)}
              </Link>
            ) : null}
          </div>
        </li>
      ))}
    </ul>
  )
}

function exploreHref(department?: string | null) {
  return department
    ? `/marketplace/assets?department=${encodeURIComponent(department)}`
    : "/marketplace/assets"
}

function HowItWorks({ steps }: { steps: TemplateStep[] }) {
  return (
    <section className="gv-card td-section" aria-labelledby="td-how">
      <h2 id="td-how">How it works</h2>
      <ol className="td-steps">
        {steps.map((step, index) => (
          <li key={`${step.id}-${index}`} className={step.approval ? "td-step gate" : "td-step"}>
            <span className="td-step-num">
              {String(index + 1).padStart(2, "0")}
              {step.approval ? " · Approval gate" : null}
            </span>
            <div className="td-step-title">{step.title}</div>
            {step.detail ? <div className="td-step-detail">{step.detail}</div> : null}
            {step.tool ? <span className="td-step-tool" title={step.tool}>{step.tool}</span> : null}
          </li>
        ))}
      </ol>
    </section>
  )
}

function WhatYouGet({ output }: { output: TemplateOutput }) {
  const report = isReportOutput(output)
  const sections = output.sections.slice(0, 4)
  const metrics = output.metrics.slice(0, 4)
  return (
    <section className="gv-card td-section" aria-labelledby="td-get">
      <div className="td-section-head">
        <h2 id="td-get">What you get</h2>
        <span className="gv-pill neutral">Sample layout</span>
      </div>
      <div className="td-output">
        <div className="td-sample" aria-label="Sample layout, not real data">
          <div className="td-sample-meta">[Date] · [Workspace]</div>
          <div className="td-sample-title">{output.title}</div>
          {output.description ? <p className="td-sample-desc">{output.description}</p> : null}
          {metrics.length > 0 ? (
            <div className="td-metrics">
              {metrics.map((metric) => (
                <div key={metric} className="td-metric">
                  <span>{metric}</span>
                  <b>[#]</b>
                </div>
              ))}
            </div>
          ) : null}
          {sections.length > 0 ? (
            sections.map((section, index) => (
              <div key={section}>
                <div className="td-sample-h">{section}</div>
                <div className="td-sample-bars" aria-hidden>
                  <div className="gv-skel" style={{ width: `${92 - index * 8}%` }} />
                  {index === 0 ? <div className="gv-skel" style={{ width: "74%" }} /> : null}
                </div>
              </div>
            ))
          ) : (
            <div className="td-sample-bars" aria-hidden style={{ marginTop: 16 }}>
              <div className="gv-skel" style={{ width: "92%" }} />
              <div className="gv-skel" style={{ width: "74%" }} />
              <div className="gv-skel" style={{ width: "66%" }} />
            </div>
          )}
        </div>
        {report ? (
          <div className="td-spot">
            {/* eslint-disable-next-line @next/next/no-img-element -- static decorative SVG */}
            <img src="/illustrations/spot-report-easel.svg" alt="" aria-hidden width={300} height={190} />
            <p>
              {output.destination
                ? `Lands in ${output.destination}, ready to read, edit and share.`
                : "Lands as a report, ready to read, edit and share."}
            </p>
          </div>
        ) : null}
      </div>
    </section>
  )
}

function WhereItFits({
  asset,
  steps,
}: {
  asset: MarketplaceAssetDetail
  steps: TemplateStep[]
}) {
  const pipelineKey = pipelineDepartmentKey(asset.department)
  const { data } = useSWR(pipelineKey ? `dept-pipeline:${pipelineKey}` : null, () =>
    departmentPipelinesApi.byDepartment(pipelineKey as string),
  )
  const pipeline = data?.pipeline as
    | {
        displayName?: string
        tagline?: string
        syncBackPolicy?: { syncTiming?: string; deferMilestoneStageId?: string | null }
      }
    | undefined
  const stages = useMemo(() => pipelineFitStages(pipeline, asset, steps), [pipeline, asset, steps])
  if (!pipeline || stages.length === 0) return null
  const deferred = pipeline.syncBackPolicy?.syncTiming === "defer_to_milestone"
  const milestone = (pipeline.syncBackPolicy?.deferMilestoneStageId ?? "milestone").replace(/_/g, " ")
  const matched = stages.some((stage) => stage.matched)
  return (
    <section className="gv-card td-section" aria-labelledby="td-fits">
      <h2 id="td-fits">Where it fits</h2>
      <p className="td-sub">
        {matched
          ? "The highlighted stages are the ones this template works in."
          : pipeline.tagline || "Your department pipeline"}
      </p>
      <div className="td-stages">
        {pipeline.displayName ? <span className="td-stages-name">{pipeline.displayName}</span> : null}
        {stages.map((stage, index) => (
          <span key={stage.stageId || stage.label} style={{ display: "contents" }}>
            <span className={stage.matched ? "td-stage on" : "td-stage"}>{stage.label}</span>
            {index < stages.length - 1 ? <span className="td-arrow" aria-hidden>→</span> : null}
          </span>
        ))}
      </div>
      {pipeline.syncBackPolicy ? (
        <div className="td-sync">
          <ShieldCheck className="h-4 w-4 shrink-0 text-[color:var(--gv-brand)]" aria-hidden />
          {deferred
            ? `Sync to system of record: deferred until ${milestone}`
            : "Sync to system of record: immediate, verified"}
        </div>
      ) : null}
    </section>
  )
}

function PairsWellWith({ asset }: { asset: MarketplaceAssetDetail }) {
  const department = asset.department ?? null
  const { data, isLoading } = useSWR(
    department ? ["marketplace-related", department] : null,
    () => marketplaceApi.listAssets({ department: department as string, limit: 8 }),
  )
  const related = (data?.assets ?? [])
    .filter((row: MarketplaceAssetSummary) => row.slug !== asset.slug)
    .slice(0, 3)
  if (!department) return null
  if (!isLoading && related.length === 0) return null
  return (
    <section aria-labelledby="td-pairs">
      <div className="td-section-head" style={{ marginBottom: 14 }}>
        <h2 id="td-pairs" style={{ margin: 0, fontSize: 20, fontWeight: 600 }}>
          Pairs well with
        </h2>
        <Link href={exploreHref(department)} className="gv-link">
          Browse Explore →
        </Link>
      </div>
      <div className="td-pairs">
        {isLoading && related.length === 0
          ? Array.from({ length: 3 }).map((_, index) => (
              <div key={index} className="gv-card" aria-hidden>
                <div className="td-pair-art" />
                <div className="td-pair-copy">
                  <div className="gv-skel" style={{ width: "40%" }} />
                  <div className="gv-skel" style={{ width: "80%", marginTop: 10 }} />
                </div>
              </div>
            ))
          : related.map((row) => {
              const art = resolveMarketArt(row)
              return (
                <Link
                  key={row.id}
                  className="gv-card gv-tpl"
                  href={`/marketplace/assets/${encodeURIComponent(row.slug)}`}
                >
                  <div className="td-pair-art">
                    {/* eslint-disable-next-line @next/next/no-img-element -- static decorative SVG */}
                    <img src={art.src} alt="" aria-hidden width={300} height={190} loading="lazy" data-illustration={art.name} />
                  </div>
                  <div className="td-pair-copy">
                    <small>{art.label}</small>
                    <strong>{row.title}</strong>
                  </div>
                </Link>
              )
            })}
      </div>
    </section>
  )
}

function AppRow({ item }: { item: MarketplaceConnectorChecklistItem }) {
  const href = item.action_url || item.connectPath || "/connectors"
  const role = item.required ? "Required" : "Optional"
  const status = item.connected ? "connected" : "not connected"
  const note = item.requirementNote || item.warning || item.discoveryLimitation
  return (
    <div className="td-app">
      <span className="td-app-logo">
        <ProviderLogo provider={item.connectorType} label={item.label} size="sm" decorative />
      </span>
      <div className="td-app-copy">
        <strong>{item.label}</strong>
        <span>
          {role} · {status}
          {note ? ` · ${note}` : ""}
        </span>
      </div>
      {item.connected ? (
        <span className="gv-pill brand">
          <Check className="h-3 w-3" aria-hidden />
          Connected
        </span>
      ) : (
        <Link className="gv-btn outline" style={{ minHeight: 40 }} href={href}>
          Connect
        </Link>
      )}
    </div>
  )
}

function readinessFor(asset: MarketplaceAssetDetail, needsPurchase: boolean) {
  const total = asset.requiredConnectorsTotal ?? 0
  const connected = asset.requiredConnectorsConnected ?? 0
  const appsLine =
    total === 0 ? "No required apps" : `${connected} of ${total} required apps connected`
  if (asset.installed) {
    return { tone: "", title: "Installed in this workspace", detail: appsLine }
  }
  if (needsPurchase) {
    return {
      tone: "amber",
      title: "Purchase required",
      detail: `${formatAssetPrice(asset)} unlocks install for this workspace`,
    }
  }
  if (!Array.isArray(asset.connectorChecklist)) {
    return { tone: "neutral", title: "Setup requirements not reported", detail: "Check again before installing" }
  }
  if (asset.canInstall) return { tone: "", title: "Ready to install", detail: appsLine }
  const missing = Math.max(0, total - connected)
  return {
    tone: "amber",
    title: missing > 0 ? `Connect ${missing} required app${missing === 1 ? "" : "s"}` : "Not ready to install",
    detail: appsLine,
  }
}

function MarketplaceAssetDetailContent() {
  const params = useParams<{ slug: string }>()
  const router = useRouter()
  const searchParams = useSearchParams()
  const slug = decodeURIComponent(params.slug)
  const { user } = useAuth()
  const { isAdmin } = useOrgAdmin()
  const [installOpen, setInstallOpen] = useState(false)
  const lock = useRef(false)
  const [uninstallOpen, setUninstallOpen] = useState(false)
  const [busy, setBusy] = useState(false)

  const { data, error, isLoading, mutate } = useSWR(
    user ? ["marketplace-asset", slug] : null,
    () => marketplaceApi.getAsset(slug),
  )
  const asset = data?.asset as MarketplaceAssetDetail | undefined

  const { data: entitlement, mutate: mutateEntitlement } = useSWR(
    user && asset ? ["marketplace-entitlement", slug] : null,
    () => marketplaceApi.assetEntitlement(slug),
  )

  useEffect(() => {
    const purchase = searchParams.get("purchase")
    if (!purchase) return
    if (purchase === "success") {
      toast.info("Checkout returned", {
        description: "Checking workspace access before installation.",
      })
      void mutateEntitlement()
      setInstallOpen(true)
    } else if (purchase === "cancelled") {
      toast.message("Checkout cancelled")
    } else if (purchase === "1") {
      setInstallOpen(true)
    }
    router.replace(`/marketplace/assets/${encodeURIComponent(slug)}`, {
      scroll: false,
    })
  }, [mutateEntitlement, router, searchParams, slug])

  const needsPurchase = Boolean(
    asset &&
      assetRequiresPurchase({
        ...asset,
        hasEntitlement: entitlement?.hasEntitlement ?? asset.hasEntitlement,
      }),
  )

  const steps = useMemo(() => (asset ? templateSteps(asset) : []), [asset])
  const output = useMemo(() => (asset ? templateOutput(asset) : null), [asset])

  const handleClone = async () => {
    if (!asset || !isAdmin || lock.current) return
    lock.current = true
    setBusy(true)
    try {
      const result = await marketplaceApi.cloneAsset(asset.slug)
      toast.success("Draft copy created", { description: result.asset.title })
    } catch (err) {
      toast.error("Clone failed", {
        description: err instanceof Error ? err.message : "Try again",
      })
    } finally {
      lock.current = false
      setBusy(false)
    }
  }

  const handleUninstall = async () => {
    if (!asset || !isAdmin || lock.current)
      throw new Error("Another asset update is pending")
    lock.current = true
    setBusy(true)
    try {
      const result = await marketplaceApi.uninstallAsset(asset.slug)
      if (!result.uninstalled)
        throw new Error(
          "The server did not confirm uninstall. Refresh the asset before retrying.",
        )
      toast.success("Asset uninstalled")
      await Promise.allSettled([mutate()])
    } catch (err) {
      throw err
    } finally {
      lock.current = false
      setBusy(false)
    }
  }

  const openInstall = useCallback(() => setInstallOpen(true), [])

  if (error && !asset) {
    return (
      <AppShell title="Asset not found">
        <div className="mx-auto max-w-2xl rounded-lg border border-destructive/30 bg-destructive/5 p-6 text-center">
          <WorkSectionErrorCard
            title="Could not load this marketplace asset"
            onRetry={() => void mutate()}
          />
          <Button className="mt-4" variant="outline" asChild>
            <Link href="/marketplace/assets">Back to catalog</Link>
          </Button>
        </div>
      </AppShell>
    )
  }

  const installLabel = asset
    ? needsPurchase
      ? `Buy & install · ${formatAssetPrice(asset)}`
      : asset.canInstall
        ? "Install to workspace"
        : "Connect apps to install"
    : "Install"

  const typeLabel = asset ? marketplaceTypeLabel(asset.assetType) : ""
  const category = asset ? departmentLabel(asset.department) : null
  const art = asset ? resolveMarketArt(asset) : null
  const cadence = asset ? templateCadence(asset) : null
  const appsPill = asset ? requiredAppsLabel(asset) : null
  const gates = approvalGateCount(steps)
  const readiness = asset ? readinessFor(asset, needsPurchase) : null
  const apps = asset?.connectorChecklist ?? []
  const hasWorkflow = steps.length > 0

  return (
    <AppShell title={asset?.title ?? "Marketplace asset"}>
      {error ? (
        <WorkSectionErrorCard
          title="Could not refresh asset details"
          message="Loaded details remain available."
          onRetry={() => void mutate()}
        />
      ) : null}
      <div
        className="relative shrink-0 pb-[calc(12rem+env(safe-area-inset-bottom))] md:pb-0"
        data-composition="discover"
      >
        <WsPage>
          <nav aria-label="Breadcrumb" className="td-crumbs">
            <Link href="/marketplace/assets">Explore</Link>
            {category ? (
              <>
                <span aria-hidden>/</span>
                <Link href={exploreHref(asset?.department)}>{category}</Link>
              </>
            ) : null}
            <span aria-hidden>/</span>
            <span aria-current="page">{asset?.title ?? "Template"}</span>
          </nav>

          {isLoading && !asset ? (
            <div aria-busy="true" role="status" aria-label="Loading template">
              <div className="gv-card" style={{ height: 320 }} />
              <div className="td-body">
                <div className="td-main">
                  <div className="gv-card td-section">
                    <div className="gv-skel" style={{ width: "30%" }} />
                    <div className="gv-skel" style={{ width: "90%", marginTop: 16 }} />
                    <div className="gv-skel" style={{ width: "70%", marginTop: 10 }} />
                  </div>
                </div>
                <div className="td-aside">
                  <div className="gv-card td-install" style={{ height: 220 }} />
                </div>
              </div>
            </div>
          ) : asset && art && readiness ? (
            <>
              <section className="gv-card gv-rise td-hero" data-testid="marketplace-asset-overview">
                <div className="td-hero-copy">
                  <div className="td-hero-eyebrow">
                    {asset.assetType === "workflow" ? "Workflow template" : typeLabel}
                    {category ? ` · ${category}` : ""}
                  </div>
                  <h1>{asset.title}</h1>
                  {asset.description || asset.businessOutcome ? (
                    <p className="td-hero-lede">{asset.description || asset.businessOutcome}</p>
                  ) : null}
                  {asset.description && asset.businessOutcome ? (
                    <p className="td-hero-outcome">{asset.businessOutcome}</p>
                  ) : null}
                  <div className="td-hero-pills">
                    <span className="gv-pill">{formatAssetPrice(asset)}</span>
                    {cadence ? <span className="gv-pill">{cadence}</span> : null}
                    {appsPill ? <span className="gv-pill">{appsPill}</span> : null}
                    {asset.installed ? <span className="gv-pill">Installed</span> : null}
                  </div>
                </div>
                <div className="td-hero-art">
                  {/* eslint-disable-next-line @next/next/no-img-element -- static decorative SVG */}
                  <img src={art.src} alt={art.alt} width={300} height={190} data-illustration={art.name} />
                </div>
              </section>

              <div className="td-body">
                <div className="td-main">
                  {hasWorkflow ? <HowItWorks steps={steps} /> : null}

                  {asset.packItems?.length ? (
                    <section className="gv-card td-section">
                      <PackContentsPreview items={asset.packItems} linkChildren />
                    </section>
                  ) : null}

                  {output ? <WhatYouGet output={output} /> : null}

                  <WhereItFits asset={asset} steps={steps} />

                  <PairsWellWith asset={asset} />

                  <section className="gv-card td-section">
                    <AssetReviewsSection
                      assetRef={asset.slug}
                      averageRating={asset.averageRating}
                      reviewCount={asset.reviewCount}
                      onStatsChange={() => void mutate()}
                    />
                  </section>
                </div>

                <aside className="td-aside" aria-label="Install">
                  <div className="gv-card td-install">
                    <div className={`td-ready ${readiness.tone}`.trim()} role="status">
                      <span className="td-ready-icon" aria-hidden>
                        {readiness.tone === "" ? (
                          <Check className="h-3.5 w-3.5" strokeWidth={2.6} />
                        ) : (
                          <AlertCircle className="h-3.5 w-3.5" strokeWidth={2.4} />
                        )}
                      </span>
                      <div className="td-ready-copy">
                        <strong>{readiness.title}</strong>
                        <div>{readiness.detail}</div>
                      </div>
                    </div>

                    <div className="hidden md:block">
                      {isAdmin && !asset.installed ? (
                        <button type="button" className="gv-btn dark td-primary" onClick={openInstall}>
                          {needsPurchase ? <ShoppingCart className="h-4 w-4" aria-hidden /> : null}
                          {installLabel}
                        </button>
                      ) : null}
                      {asset.installed ? (
                        <Link className="gv-btn dark td-primary" href="/marketplace/installed">
                          <CheckCircle2 className="h-4 w-4" aria-hidden />
                          Open installed
                        </Link>
                      ) : null}
                      {isAdmin ? (
                        <button
                          type="button"
                          className="gv-btn outline td-secondary"
                          disabled={busy}
                          onClick={handleClone}
                        >
                          {busy ? (
                            <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
                          ) : (
                            <Copy className="h-4 w-4" aria-hidden />
                          )}
                          Clone as draft
                        </button>
                      ) : null}
                      {isAdmin && asset.installed ? (
                        <button
                          type="button"
                          className="gv-btn danger td-secondary"
                          disabled={busy}
                          onClick={() => setUninstallOpen(true)}
                        >
                          <Trash2 className="h-4 w-4" aria-hidden />
                          Uninstall
                        </button>
                      ) : null}
                    </div>

                    {!isAdmin && !asset.installed ? (
                      needsPurchase ? (
                        <div className="mt-4">
                          <NonAdminPurchaseNotice />
                        </div>
                      ) : (
                        <p className="td-note">An org admin or owner installs templates for this workspace.</p>
                      )
                    ) : null}

                    {hasWorkflow && !asset.installed ? (
                      <p className="td-note">
                        Installs without a schedule. Nothing runs until you start a run or add a schedule.
                      </p>
                    ) : null}

                    {asset.blockers?.length ? (
                      <div className="mt-4">
                        <BlockerList blockers={asset.blockers} />
                      </div>
                    ) : null}
                  </div>

                  {apps.length > 0 ? (
                    <div className="gv-card td-panel">
                      <div className="gv-eyebrow">Apps</div>
                      {apps.map((item) => (
                        <AppRow key={item.connectorType} item={item} />
                      ))}
                    </div>
                  ) : null}

                  <div className="gv-card td-panel">
                    <div className="gv-eyebrow">Details</div>
                    <dl className="td-details">
                      <dt>Type</dt>
                      <dd>{typeLabel}</dd>
                      <dt>Category</dt>
                      <dd>{category ?? "All departments"}</dd>
                      <dt>Price</dt>
                      <dd>{formatAssetPrice(asset)}</dd>
                      <dt>Approval gates</dt>
                      <dd>{hasWorkflow ? (gates > 0 ? gates : "None in definition") : "Not reported"}</dd>
                      {asset.packItems?.length ? (
                        <>
                          <dt>Included components</dt>
                          <dd>{asset.packItems.length}</dd>
                        </>
                      ) : null}
                      {asset.estimatedHoursSaved != null ? (
                        <>
                          <dt>{ESTIMATED_HOURS_SAVED_MONTHLY}</dt>
                          <dd>{asset.estimatedHoursSaved}h</dd>
                        </>
                      ) : null}
                      {asset.publisherDisplayName ? (
                        <>
                          <dt>Publisher</dt>
                          <dd>{asset.publisherDisplayName}</dd>
                        </>
                      ) : null}
                      {asset.currentVersion != null ? (
                        <>
                          <dt>Version</dt>
                          <dd>v{asset.currentVersion}</dd>
                        </>
                      ) : null}
                    </dl>
                  </div>
                </aside>
              </div>
            </>
          ) : null}
        </WsPage>

        {asset && (isAdmin || asset.installed) ? (
          <div
            className="fixed inset-x-0 bottom-[calc(3.5rem+env(safe-area-inset-bottom))] z-20 border-t border-[color:var(--g-border-default)] bg-[color:var(--g-canvas)]/95 px-4 py-3 backdrop-blur-sm md:hidden"
            data-testid="marketplace-mobile-actions"
            data-gravitre-mobile-action-dock
          >
            <div className="mx-auto flex max-w-5xl items-center gap-2">
              {isAdmin && !asset.installed ? (
                <Button
                  className="min-h-11 min-w-0 flex-1 rounded-[10px] font-semibold"
                  onClick={openInstall}
                >
                  {needsPurchase ? (
                    <>
                      <ShoppingCart
                        className="mr-1.5 h-4 w-4 shrink-0"
                        aria-hidden
                      />
                      <span className="truncate">{installLabel}</span>
                    </>
                  ) : (
                    <span className="truncate">{installLabel}</span>
                  )}
                </Button>
              ) : null}
              {asset.installed ? (
                <Button
                  className="min-h-11 min-w-0 flex-1 rounded-[10px] font-semibold"
                  asChild
                >
                  <Link href="/marketplace/installed">Open installed</Link>
                </Button>
              ) : null}
              {isAdmin ? (
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <Button
                      variant="outline"
                      size="icon"
                      className="min-h-11 min-w-11 shrink-0 rounded-[10px]"
                      aria-label="More asset actions"
                      disabled={busy}
                    >
                      {busy ? (
                        <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
                      ) : (
                        <MoreHorizontal className="h-4 w-4" aria-hidden />
                      )}
                    </Button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="end" side="top" className="z-50">
                    <DropdownMenuItem
                      disabled={busy}
                      onSelect={() => void handleClone()}
                    >
                      <Copy className="mr-2 h-3.5 w-3.5" aria-hidden />
                      Clone as draft
                    </DropdownMenuItem>
                    {asset.installed ? (
                      <DropdownMenuItem
                        className="text-destructive focus:text-destructive"
                        disabled={busy}
                        onSelect={() => {
                          setUninstallOpen(true)
                        }}
                      >
                        <Trash2 className="mr-2 h-3.5 w-3.5" aria-hidden />
                        Uninstall
                      </DropdownMenuItem>
                    ) : null}
                  </DropdownMenuContent>
                </DropdownMenu>
              ) : null}
            </div>
          </div>
        ) : null}
      </div>

      <InstallStepperSheet
        asset={asset ?? null}
        open={installOpen}
        onOpenChange={setInstallOpen}
        onComplete={() => void mutate()}
        isAdmin={isAdmin}
      />
      {uninstallOpen && asset ? (
        <MarketplaceDecisionDialog
          title={`Uninstall ${asset.title}?`}
          description="This removes the marketplace install record from your organization. Review created resources separately before deleting agents, workflows or knowledge."
          actionLabel="Confirm uninstall"
          destructive
          onCancel={() => setUninstallOpen(false)}
          onConfirm={handleUninstall}
        />
      ) : null}
    </AppShell>
  )
}

export default function MarketplaceAssetDetailPage() {
  return (
    <Suspense
      fallback={
        <div className="grid min-h-[40vh] place-items-center text-muted-foreground">
          <Loader2 className="h-8 w-8 animate-spin" aria-hidden />
        </div>
      }
    >
      <MarketplaceAssetDetailContent />
    </Suspense>
  )
}
