"use client"

import { Suspense, useCallback, useEffect, useMemo, useState } from "react"
import Link from "next/link"
import { useParams } from "next/navigation"
import useSWR from "swr"
import { AppShell } from "@/components/gravitre/app-shell"
import { AssetReviewsSection } from "@/components/marketplace/asset-reviews-section"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet"
import { marketplaceApi } from "@/lib/api"
import { useAuth } from "@/lib/auth-context"
import {
  AlertCircle,
  ArrowLeft,
  CheckCircle2,
  ChevronRight,
  Copy,
  ExternalLink,
  Loader2,
  Plug,
  ShoppingCart,
} from "lucide-react"
import { toast } from "sonner"
import { toastMarketplaceInstallFailure } from "@/lib/marketplace-install-error"
import type {
  MarketplaceAssetDetail,
  MarketplaceAssetInstallCheck,
  MarketplaceAssetSummary,
  MarketplaceConnectorChecklistItem,
  MarketplaceInstallBlocker,
} from "@/types/api"

type InstallStep = "check" | "confirm" | "installing" | "done"

function formatPrice(cents?: number, currency = "usd") {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: currency.toUpperCase(),
  }).format((cents ?? 0) / 100)
}

function checklistTone(item: MarketplaceConnectorChecklistItem) {
  if (item.connected) return "text-success"
  if (item.required) return "text-destructive"
  return "text-warning"
}

function ConnectorChecklist({ items }: { items: MarketplaceConnectorChecklistItem[] }) {
  if (!items.length) return null
  return (
    <ul className="space-y-2">
      {items.map((item) => (
        <li key={item.connectorType} className="flex items-start justify-between gap-2 text-sm">
          <div className="flex items-center gap-2">
            {item.connected ? (
              <CheckCircle2 className={`h-4 w-4 shrink-0 ${checklistTone(item)}`} aria-hidden />
            ) : (
              <Plug className={`h-4 w-4 shrink-0 ${checklistTone(item)}`} aria-hidden />
            )}
            <span>{item.label || item.connectorType}</span>
          </div>
          {!item.connected ? (
            <Button size="sm" variant="outline" asChild>
              <Link href={item.action_url || item.connectPath}>Connect</Link>
            </Button>
          ) : null}
        </li>
      ))}
    </ul>
  )
}

function BlockerList({ blockers }: { blockers: MarketplaceInstallBlocker[] }) {
  if (!blockers.length) return null
  return (
    <ul className="space-y-2 rounded-lg border border-destructive/30 bg-destructive/5 p-3 text-sm">
      {blockers.map((blocker) => (
        <li key={blocker.connector} className="flex items-start gap-2">
          <AlertCircle className="mt-0.5 h-4 w-4 shrink-0 text-destructive" aria-hidden />
          <div className="flex-1">
            <p>{blocker.reason}</p>
            {blocker.action_url ? (
              <Link href={blocker.action_url} className="text-primary underline-offset-4 hover:underline">
                Connect {blocker.connector}
              </Link>
            ) : null}
          </div>
        </li>
      ))}
    </ul>
  )
}

function PurchaseButton({
  asset,
  check,
  onPurchased,
}: {
  asset: MarketplaceAssetSummary
  check: MarketplaceAssetInstallCheck
  onPurchased: () => void
}) {
  const [busy, setBusy] = useState(false)
  const runCheckout = async () => {
    setBusy(true)
    try {
      const origin = window.location.origin
      const result = await marketplaceApi.assetCheckout(asset.slug, {
        successUrl: `${origin}/marketplace/assets/${encodeURIComponent(asset.slug)}?purchase=success`,
        cancelUrl: `${origin}/marketplace/assets/${encodeURIComponent(asset.slug)}?purchase=cancelled`,
      })
      if (result.checkoutUrl) {
        window.location.href = result.checkoutUrl
        return
      }
      onPurchased()
    } catch (err) {
      toast.error("Checkout failed", {
        description: err instanceof Error ? err.message : "Try again",
      })
    } finally {
      setBusy(false)
    }
  }
  return (
    <Button className="w-full" disabled={busy} onClick={() => void runCheckout()}>
      {busy ? (
        <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden />
      ) : (
        <ShoppingCart className="mr-2 h-4 w-4" aria-hidden />
      )}
      Purchase {formatPrice(check.priceCents, check.currency)} to unlock install
    </Button>
  )
}

function InstallStepperSheet({
  asset,
  open,
  onOpenChange,
  onComplete,
  isAdmin,
}: {
  asset: MarketplaceAssetSummary | null
  open: boolean
  onOpenChange: (open: boolean) => void
  onComplete: () => void
  isAdmin: boolean
}) {
  const [step, setStep] = useState<InstallStep>("check")
  const [installResult, setInstallResult] = useState<Record<string, unknown> | null>(null)

  const checkKey = open && asset ? ["marketplace-install-check", asset.id] : null
  const { data: check, isLoading: checkLoading, mutate: refreshCheck } = useSWR(
    checkKey,
    () => marketplaceApi.installCheck(asset!.id),
    { revalidateOnFocus: false },
  )

  const handleOpenChange = (next: boolean) => {
    if (!next) {
      setStep("check")
      setInstallResult(null)
    }
    onOpenChange(next)
  }

  const activeStep: InstallStep =
    step === "installing" || step === "done"
      ? step
      : step === "check" && check && !checkLoading
        ? check.canInstall
          ? "confirm"
          : "check"
        : step

  const runInstall = async () => {
    if (!asset) return
    setStep("installing")
    try {
      const result = await marketplaceApi.installAsset(asset.slug)
      setInstallResult(result.entities ?? {})
      setStep("done")
      onComplete()
      toast.success(`${asset.title} installed`)
    } catch (err) {
      toastMarketplaceInstallFailure(err, {
        blockerActionUrl: check?.blockers?.[0]?.action_url,
      })
      await refreshCheck()
      setStep("check")
    }
  }

  return (
    <Sheet open={open} onOpenChange={handleOpenChange}>
      <SheetContent side="right" className="flex w-full flex-col sm:max-w-md">
        <SheetHeader>
          <SheetTitle>Install {asset?.title ?? "asset"}</SheetTitle>
          <SheetDescription>Provision agents, workflows, and knowledge into your org.</SheetDescription>
        </SheetHeader>
        <div className="flex-1 space-y-4 overflow-y-auto px-4">
          {checkLoading ? (
            <div className="grid place-items-center py-8">
              <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" aria-hidden />
            </div>
          ) : null}
          {!checkLoading && activeStep === "check" && !check?.canInstall ? (
            <>
              <BlockerList blockers={check?.blockers ?? []} />
              <ConnectorChecklist items={check?.connectorChecklist ?? asset?.connectorChecklist ?? []} />
              {check?.requiresPayment && !check?.hasEntitlement && asset && isAdmin ? (
                <PurchaseButton asset={asset} check={check} onPurchased={() => void refreshCheck()} />
              ) : null}
            </>
          ) : null}
          {!checkLoading && (activeStep === "confirm" || step === "installing") ? (
            <ConnectorChecklist items={check?.connectorChecklist ?? asset?.connectorChecklist ?? []} />
          ) : null}
          {activeStep === "done" ? (
            <div className="space-y-3 rounded-lg border border-success/30 bg-success/5 p-4 text-sm">
              <p className="flex items-center gap-2 font-medium text-success">
                <CheckCircle2 className="h-4 w-4" aria-hidden />
                Installation complete
              </p>
              {installResult?.workflowId ? (
                <Button size="sm" variant="outline" asChild>
                  <Link href={`/workflows/${String(installResult.workflowId)}/builder`}>
                    Open workflow
                    <ExternalLink className="ml-1.5 h-3.5 w-3.5" aria-hidden />
                  </Link>
                </Button>
              ) : null}
            </div>
          ) : null}
        </div>
        <SheetFooter className="border-t pt-4">
          {activeStep === "confirm" ? (
            <>
              <Button variant="outline" onClick={() => handleOpenChange(false)}>
                Cancel
              </Button>
              <Button onClick={runInstall}>Confirm install</Button>
            </>
          ) : null}
          {step === "installing" ? (
            <Button disabled>
              <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden />
              Installing…
            </Button>
          ) : null}
          {activeStep === "done" ? (
            <Button onClick={() => handleOpenChange(false)}>Done</Button>
          ) : null}
        </SheetFooter>
      </SheetContent>
    </Sheet>
  )
}

function MarketplaceAssetDetailContent() {
  const params = useParams<{ slug: string }>()
  const slug = decodeURIComponent(params.slug)
  const { user } = useAuth()
  const role = user?.role
  const isAdmin = role === "admin" || role === "owner"
  const [installOpen, setInstallOpen] = useState(false)
  const [busy, setBusy] = useState(false)

  const { data, error, isLoading, mutate } = useSWR(
    user ? ["marketplace-asset", slug] : null,
    () => marketplaceApi.getAsset(slug),
  )
  const asset = data?.asset as MarketplaceAssetDetail | undefined

  const handleClone = async () => {
    if (!asset) return
    setBusy(true)
    try {
      const result = await marketplaceApi.cloneAsset(asset.slug)
      toast.success("Draft copy created", { description: result.asset.title })
    } catch (err) {
      toast.error("Clone failed", { description: err instanceof Error ? err.message : "Try again" })
    } finally {
      setBusy(false)
    }
  }

  const openInstall = useCallback(() => setInstallOpen(true), [])

  if (error) {
    return (
      <AppShell title="Asset not found">
        <div className="mx-auto max-w-2xl rounded-lg border border-destructive/30 bg-destructive/5 p-6 text-center">
          <p className="text-sm text-destructive">Could not load this marketplace asset.</p>
          <Button className="mt-4" variant="outline" asChild>
            <Link href="/marketplace/assets">Back to catalog</Link>
          </Button>
        </div>
      </AppShell>
    )
  }

  return (
    <AppShell title={asset?.title ?? "Marketplace asset"}>
      <div className="mx-auto max-w-3xl space-y-6">
        <Button variant="ghost" size="sm" asChild className="-ml-2">
          <Link href="/marketplace/assets">
            <ArrowLeft className="mr-1.5 h-4 w-4" aria-hidden />
            Back to catalog
          </Link>
        </Button>

        {isLoading && !asset ? (
          <div className="space-y-4">
            <Skeleton className="h-8 w-2/3" />
            <Skeleton className="h-24 w-full" />
          </div>
        ) : asset ? (
          <>
            <header className="space-y-3">
              <div className="flex flex-wrap gap-2">
                <Badge variant="outline">{asset.assetType.replace(/_/g, " ")}</Badge>
                {asset.department ? <Badge variant="secondary">{asset.department}</Badge> : null}
                {asset.pricingType !== "free" && (asset.priceCents ?? 0) > 0 ? (
                  <Badge variant="outline">{formatPrice(asset.priceCents, "usd")}</Badge>
                ) : null}
                {asset.installed ? <Badge>Installed</Badge> : null}
              </div>
              <h1 className="text-2xl font-semibold text-foreground">{asset.title}</h1>
              {asset.description ? (
                <p className="text-sm text-muted-foreground text-pretty">{asset.description}</p>
              ) : null}
            </header>

            {asset.blockers?.length ? <BlockerList blockers={asset.blockers} /> : null}

            {asset.connectorChecklist?.length ? (
              <div className="rounded-lg border bg-muted/20 p-4">
                <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                  Connector checklist
                </p>
                <ConnectorChecklist items={asset.connectorChecklist} />
              </div>
            ) : null}

            {asset.packItems?.length ? (
              <div className="rounded-lg border p-4">
                <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                  Pack contents
                </p>
                <ul className="space-y-2 text-sm">
                  {asset.packItems.map((item) => (
                    <li key={item.child.id} className="flex items-center justify-between gap-2">
                      <Link
                        href={`/marketplace/assets/${encodeURIComponent(item.child.slug)}`}
                        className="text-primary hover:underline"
                      >
                        {item.child.title}
                      </Link>
                      <Badge variant="outline" className="text-[10px]">
                        {item.child.assetType}
                      </Badge>
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}

            <div className="flex flex-wrap gap-2">
              {isAdmin && !asset.installed ? (
                <Button disabled={!asset.canInstall} onClick={openInstall}>
                  {asset.canInstall ? "Install" : "Connect apps to install"}
                </Button>
              ) : null}
              <Button variant="secondary" disabled={busy} onClick={handleClone}>
                {busy ? (
                  <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" aria-hidden />
                ) : (
                  <Copy className="mr-1.5 h-3.5 w-3.5" aria-hidden />
                )}
                Clone
              </Button>
              {asset.installed ? (
                <Button variant="outline" asChild>
                  <Link href="/marketplace/installed">
                    Manage installed
                    <ChevronRight className="ml-1 h-3.5 w-3.5" aria-hidden />
                  </Link>
                </Button>
              ) : null}
            </div>

            <AssetReviewsSection
              assetRef={asset.slug}
              averageRating={asset.averageRating}
              reviewCount={asset.reviewCount}
              onStatsChange={() => void mutate()}
            />
          </>
        ) : null}
      </div>

      <InstallStepperSheet
        asset={asset ?? null}
        open={installOpen}
        onOpenChange={setInstallOpen}
        onComplete={() => void mutate()}
        isAdmin={isAdmin}
      />
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
