"use client"

import { useState } from "react"
import Link from "next/link"
import useSWR from "swr"
import { motion, useReducedMotion } from "framer-motion"
import { AssetPurchaseButton } from "@/components/marketplace/asset-purchase-button"
import {
  ConnectorChecklist,
  NonAdminPurchaseNotice,
  assetRequiresPurchase,
  formatAssetPrice,
} from "@/components/marketplace/marketplace-asset-commerce"
import { Button } from "@/components/ui/button"
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet"
import { marketplaceApi } from "@/lib/api"
import { DepartmentPipelineByDepartment } from "@/components/marketplace/department-pipeline-panel"
import { toastMarketplaceInstallFailure } from "@/lib/marketplace-install-error"
import { cn } from "@/lib/utils"
import type {
  MarketplaceAssetInstallResult,
  MarketplaceAssetSummary,
  MarketplaceInstallBlocker,
  MarketplaceInstallDeepLink,
} from "@/types/api"
import {
  AlertCircle,
  ArrowRight,
  Bot,
  CheckCircle2,
  Database,
  ExternalLink,
  Loader2,
  Package,
  Sparkles,
  Workflow,
} from "lucide-react"
import { toast } from "sonner"

type InstallStep = "check" | "confirm" | "installing" | "done"

function BlockerList({ blockers }: { blockers: MarketplaceInstallBlocker[] }) {
  if (!blockers.length) return null
  return (
    <ul className="space-y-2 rounded-2xl border border-destructive/30 bg-destructive/5 p-3 text-sm">
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

function linkIcon(entityType: string) {
  if (entityType === "workflow") return Workflow
  if (entityType === "rag_source") return Database
  if (entityType === "operator" || entityType === "agent") return Bot
  return Package
}

function linkHref(link: MarketplaceInstallDeepLink): string {
  if (link.entityType === "workflow") return `${link.path}/builder`
  return link.path
}

export function InstallSuccessPanel({
  assetTitle,
  deepLinks,
  entities,
  department,
}: {
  assetTitle: string
  deepLinks: MarketplaceInstallDeepLink[]
  entities?: Record<string, unknown> | null
  department?: string | null
}) {
  const reduced = useReducedMotion()
  const links: MarketplaceInstallDeepLink[] = []
  if (deepLinks.length > 0) {
    for (const link of deepLinks) {
      if (link.label === "Primary" && deepLinks.length > 1) continue
      links.push(link)
    }
  } else if (entities) {
    const agentId = entities.agentId || entities.operatorId
    const workflowId = entities.workflowId
    if (typeof agentId === "string" && agentId) {
      links.push({ label: "Agent", entityType: "agent", entityId: agentId, path: `/agents/${agentId}` })
    }
    if (typeof workflowId === "string" && workflowId) {
      links.push({
        label: "Workflow",
        entityType: "workflow",
        entityId: workflowId,
        path: `/workflows/${workflowId}`,
      })
    }
  }

  return (
    <motion.div
      initial={reduced ? false : { opacity: 0, y: 10, scale: 0.98 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      className="relative overflow-hidden rounded-3xl border border-success/25 bg-gradient-to-br from-success/10 via-card to-primary/5 p-5"
    >
      <div
        aria-hidden
        className="pointer-events-none absolute -right-10 -top-12 h-40 w-40 rounded-full bg-success/20 blur-3xl"
      />
      <div className="relative space-y-4">
        <div className="flex items-start gap-3">
          <span className="grid h-11 w-11 place-items-center rounded-2xl bg-success/15 text-success shadow-inner">
            <Sparkles className="h-5 w-5" aria-hidden />
          </span>
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-success/80">
              Live in your workspace
            </p>
            <h3 className="mt-1 text-lg font-semibold tracking-tight text-foreground">
              {assetTitle} is installed
            </h3>
            <p className="mt-1 text-sm text-muted-foreground">
              We added it to your Gravitre instance. A confirmation is in your notifications
              {links.length ? " — jump in below." : "."}
            </p>
          </div>
        </div>

        {links.length ? (
          <div className="grid gap-2">
            {links.map((link) => {
              const Icon = linkIcon(link.entityType)
              return (
                <Button
                  key={`${link.entityType}:${link.entityId}:${link.path}`}
                  asChild
                  variant="outline"
                  // Intentional exception to the pill rule (RADIUS.control): this
                  // is a full-width, h-auto, two-line navigation card that happens
                  // to be built on Button, not a compact click target. Card radius
                  // is correct — a pill on a tall block reads as a lozenge.
                  className="h-auto justify-between rounded-2xl border-border/70 bg-background/70 px-4 py-3 text-left shadow-sm backdrop-blur hover:border-primary/40 hover:bg-background"
                >
                  <Link href={linkHref(link)}>
                    <span className="flex min-w-0 items-center gap-3">
                      <span className="grid h-9 w-9 place-items-center rounded-xl bg-muted/60">
                        <Icon className="h-4 w-4 text-foreground" aria-hidden />
                      </span>
                      <span className="min-w-0">
                        <span className="block text-sm font-medium text-foreground">{link.label}</span>
                        <span className="block truncate text-[11px] text-muted-foreground">{link.path}</span>
                      </span>
                    </span>
                    <ExternalLink className="h-4 w-4 shrink-0 text-muted-foreground" aria-hidden />
                  </Link>
                </Button>
              )
            })}
          </div>
        ) : null}

        {department ? (
          <div className="mt-1">
            <DepartmentPipelineByDepartment department={department} />
          </div>
        ) : null}

        <div className="flex flex-wrap gap-2">
          <Button asChild size="sm" className="rounded-full">
            <Link href="/marketplace/installed">
              View installed
              <ArrowRight className="ml-1.5 h-3.5 w-3.5" aria-hidden />
            </Link>
          </Button>
          <Button asChild size="sm" variant="ghost" className="rounded-full">
            <Link href="/agents">Agents</Link>
          </Button>
          <Button asChild size="sm" variant="ghost" className="rounded-full">
            <Link href="/workflows">Workflows</Link>
          </Button>
        </div>
      </div>
    </motion.div>
  )
}

export function InstallStepperSheet({
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
  const [installResult, setInstallResult] = useState<MarketplaceAssetInstallResult | null>(null)

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
      setInstallResult(result)
      setStep("done")
      onComplete()
      toast.success(`${asset.title} is live in your workspace`)
    } catch (err) {
      toastMarketplaceInstallFailure(err, {
        blockerActionUrl: check?.blockers?.[0]?.action_url,
      })
      await refreshCheck()
      setStep("check")
    }
  }

  const checklist = check?.connectorChecklist ?? asset?.connectorChecklist ?? []
  const blockers = check?.blockers ?? []
  const needsPurchase = asset ? assetRequiresPurchase(asset) : false

  return (
    <Sheet open={open} onOpenChange={handleOpenChange}>
      <SheetContent side="right" className="flex w-full flex-col border-l border-border/60 bg-background/95 sm:max-w-md">
        <SheetHeader className="space-y-2 border-b border-border/50 pb-4">
          <p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-muted-foreground">
            Install into workspace
          </p>
          <SheetTitle className="text-xl tracking-tight">{asset?.title ?? "Asset"}</SheetTitle>
          <SheetDescription>
            We&apos;ll provision agents, workflows, and knowledge — then notify you when it&apos;s ready.
          </SheetDescription>
        </SheetHeader>

        <div className="flex-1 space-y-4 overflow-y-auto px-1 py-4">
          <ol className="flex gap-2 text-[11px] font-semibold uppercase tracking-[0.16em] text-muted-foreground">
            {(["check", "confirm", "done"] as const).map((id, idx) => (
              <li
                key={id}
                className={cn(
                  "flex items-center gap-1.5",
                  (activeStep === id ||
                    (step === "installing" && id === "confirm") ||
                    (activeStep === "done" && id === "done")) &&
                    "text-foreground",
                )}
              >
                <span
                  className={cn(
                    "grid h-6 w-6 place-items-center rounded-full border text-[10px]",
                    activeStep === id || (activeStep === "done" && id === "done")
                      ? "border-primary bg-primary text-primary-foreground"
                      : "border-border",
                  )}
                >
                  {activeStep === "done" && id === "done" ? (
                    <CheckCircle2 className="h-3.5 w-3.5" aria-hidden />
                  ) : (
                    idx + 1
                  )}
                </span>
                {id}
              </li>
            ))}
          </ol>

          {checkLoading ? (
            <div className="grid place-items-center py-10">
              <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" aria-hidden />
            </div>
          ) : null}

          {!checkLoading && activeStep === "check" && !check?.canInstall ? (
            <>
              {!isAdmin && needsPurchase ? <NonAdminPurchaseNotice /> : null}
              <BlockerList blockers={blockers} />
              <ConnectorChecklist items={checklist} />
              {check?.requiresPayment && !check?.hasEntitlement && asset && isAdmin ? (
                <AssetPurchaseButton asset={asset} check={check} onPurchased={() => void refreshCheck()} />
              ) : null}
            </>
          ) : null}

          {!checkLoading && (activeStep === "confirm" || step === "installing") ? (
            <>
              <div className="rounded-2xl border border-border/70 bg-muted/20 p-4 text-sm text-muted-foreground">
                Required apps are connected. Confirm to add this pack to your org — agents and workflows will appear
                immediately.
              </div>
              <ConnectorChecklist items={checklist} />
            </>
          ) : null}

          {activeStep === "done" && asset ? (
            <InstallSuccessPanel
              assetTitle={asset.title}
              deepLinks={installResult?.deepLinks ?? []}
              entities={installResult?.entities}
              department={asset.department}
            />
          ) : null}
        </div>

        <SheetFooter className="border-t border-border/50 pt-4">
          {activeStep === "check" && !check?.canInstall ? (
            <Button variant="outline" className="rounded-full" onClick={() => handleOpenChange(false)}>
              Close
            </Button>
          ) : null}
          {activeStep === "confirm" ? (
            <>
              <Button variant="outline" className="rounded-full" onClick={() => handleOpenChange(false)}>
                Cancel
              </Button>
              <Button className="rounded-full" onClick={runInstall}>
                Confirm install
                {asset && needsPurchase ? ` · ${formatAssetPrice(asset)}` : ""}
              </Button>
            </>
          ) : null}
          {step === "installing" ? (
            <Button disabled className="rounded-full">
              <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden />
              Installing…
            </Button>
          ) : null}
          {activeStep === "done" ? (
            <Button className="rounded-full" onClick={() => handleOpenChange(false)}>
              Done
            </Button>
          ) : null}
        </SheetFooter>
      </SheetContent>
    </Sheet>
  )
}
