"use client"

import { useRef, useState } from "react"
import Link from "next/link"
import useSWR from "swr"
import { AppShell } from "@/components/gravitre/app-shell"
import {
  GravitreEmpty,
  GravitreMetric,
  GravitrePageHeader,
  GravitreSurface,
} from "@/components/gravitre/nodus-product"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { marketplaceApi } from "@/lib/api"
import { DepartmentPipelineByDepartment } from "@/components/marketplace/department-pipeline-panel"
import { PackContentsPreview } from "@/components/marketplace/marketplace-asset-commerce"
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet"
import { useIsMobile } from "@/hooks/use-mobile"
import { useAuth } from "@/lib/auth-context"
import { useOrgAdmin } from "@/lib/use-org-admin"
import { cn } from "@/lib/utils"
import {
  Package,
  ArrowLeft,
  ArrowRight,
  CheckCircle2,
  AlertTriangle,
  Loader2,
  Trash2,
} from "lucide-react"
import { toast } from "sonner"
import type { MarketplaceInstall } from "@/types/api"

function formatInstalledAt(value?: string | null) {
  if (!value) return null
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return null
  return date.toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
  })
}

function InstalledAssetRow({
  install,
  isSelected,
  onSelect,
}: {
  install: MarketplaceInstall
  isSelected: boolean
  onSelect: () => void
}) {
  const asset = install.asset
  const department = asset?.department ?? "Department not reported"
  const installedAt = formatInstalledAt(install.installedAt)
  return (
    <li>
      <button
        type="button"
        aria-pressed={isSelected}
        onClick={onSelect}
        className={cn(
          "flex min-h-11 w-full items-start justify-between gap-3 rounded-sm px-3 py-3 text-left focus-visible:outline-2 focus-visible:outline-offset-[-2px] focus-visible:outline-[color:var(--g-brand)]",
          isSelected
            ? "bg-[color:var(--g-surface-2)]"
            : "hover:bg-[color:var(--g-surface-2)]/50",
        )}
      >
        <span className="min-w-0">
          <span className="block text-sm font-medium text-foreground">
            {asset?.title ?? "Installed asset"}
          </span>
          <span className="mt-0.5 block text-xs capitalize text-muted-foreground">
            {department.replace(/-/g, " ")}
            {installedAt ? ` · ${installedAt}` : ""}
          </span>
        </span>
      </button>
    </li>
  )
}

function InstalledInspector({
  install,
  busy,
  onUninstall,
  isAdmin,
}: {
  install: MarketplaceInstall
  busy: string | null
  onUninstall: (install: MarketplaceInstall) => void
  isAdmin: boolean
}) {
  const asset = install.asset
  const department = asset?.department ?? "Department not reported"
  const installedAt = formatInstalledAt(install.installedAt)
  const slug = asset?.slug
  const {
    data: packDetail,
    error: packError,
    isLoading: packLoading,
    mutate: refreshPack,
  } = useSWR(slug ? ["marketplace-asset", slug] : null, () =>
    marketplaceApi.getAsset(slug!),
  )
  const agentCount =
    install.metadata?.agentIds?.length ??
    (install.metadata?.agentId || install.metadata?.operatorId
      ? 1
      : "Not reported")
  const workflowCount =
    install.metadata?.workflowIds?.length ??
    (install.metadata?.workflowId ? 1 : "Not reported")
  const sourceCount =
    install.metadata?.ragSourceIds?.length ??
    (install.metadata?.ragSourceId ? 1 : "Not reported")
  const deepLinks = (install.deepLinks ?? []).filter(
    (link) =>
      !(link.label === "Primary" && (install.deepLinks?.length ?? 0) > 1),
  )

  return (
    <div
      className="space-y-4 p-4"
      data-review-surface="marketplace-ops-inspect"
    >
      <div>
        <p className="text-xs font-medium text-muted-foreground">Install</p>
        <h2 className="mt-1 break-words font-[family-name:var(--font-space-grotesk)] text-xl font-medium text-foreground">
          {asset?.title ?? "Installed asset"}
        </h2>
        <p className="mt-1 text-xs capitalize text-muted-foreground">
          {department.replace(/-/g, " ")}
          {installedAt ? ` · Installed ${installedAt}` : ""}
        </p>
      </div>
      {deepLinks.length ? (
        <ul className="divide-y divide-divide border-y border-divide text-sm">
          {deepLinks.map((link) => (
            <li key={`${link.entityType}:${link.entityId}:${link.path}`}>
              <Link
                href={
                  link.entityType === "workflow"
                    ? `${link.path}/builder`
                    : link.path
                }
                className="flex min-h-11 items-center justify-between gap-3 rounded-sm py-2 hover:underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[color:var(--g-brand)]"
              >
                <span className="min-w-0 break-words">{link.label}</span>
                <ArrowRight
                  className="h-3.5 w-3.5 shrink-0 text-muted-foreground"
                  aria-hidden
                />
              </Link>
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-sm text-muted-foreground">
          {agentCount} agents · {workflowCount} workflows · {sourceCount}{" "}
          sources
        </p>
      )}
      {packLoading ? (
        <p role="status" className="text-sm text-muted-foreground">
          Loading pack contents…
        </p>
      ) : null}
      {packError ? (
        <div role="alert" className="space-y-2 text-sm">
          <p>Could not load pack contents.</p>
          <Button
            variant="outline"
            size="sm"
            onClick={() => void refreshPack()}
          >
            Retry contents
          </Button>
        </div>
      ) : null}
      {packDetail ? (
        <PackContentsPreview
          items={packDetail?.asset?.packItems}
          compact
          linkChildren
        />
      ) : null}
      <DepartmentPipelineByDepartment department={department} />
      <div className="flex flex-wrap gap-2">
        {slug ? (
          <Button size="sm" asChild data-review-cta="manage-install">
            <Link href={`/marketplace/assets/${encodeURIComponent(slug)}`}>
              Manage
              <ArrowRight className="ml-1 h-4 w-4" aria-hidden />
            </Link>
          </Button>
        ) : null}
        {slug && isAdmin ? (
          <Button
            variant="ghost"
            size="sm"
            className="text-destructive hover:text-destructive"
            disabled={Boolean(busy)}
            onClick={() => onUninstall(install)}
          >
            {busy === install.id ? (
              <Loader2
                className="mr-1.5 h-3.5 w-3.5 animate-spin"
                aria-hidden
              />
            ) : (
              <Trash2 className="mr-1.5 h-3.5 w-3.5" aria-hidden />
            )}
            Uninstall
          </Button>
        ) : null}
      </div>
    </div>
  )
}

function InstalledContent() {
  const { user } = useAuth()
  const { isAdmin } = useOrgAdmin()
  const useSheetInspector = useIsMobile(1024)
  const lock = useRef(false)
  const [uninstallTarget, setUninstallTarget] =
    useState<MarketplaceInstall | null>(null)
  const [uninstallError, setUninstallError] = useState<string | null>(null)
  const [busy, setBusy] = useState<string | null>(null)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const { data, error, isLoading, mutate } = useSWR(
    user ? "marketplace-installs" : null,
    () => marketplaceApi.listInstalls({ status: "active", limit: 100 }),
  )

  const installed = data?.installs ?? []
  const selected = installed.find((row) => row.id === selectedId) ?? null

  const handleUninstall = async (install: MarketplaceInstall) => {
    const slug = install.asset?.slug
    if (!slug || !isAdmin || lock.current) return
    lock.current = true
    setUninstallError(null)
    setBusy(install.id)
    try {
      const result = await marketplaceApi.uninstallAsset(slug)
      if (!result.uninstalled)
        throw new Error(
          "The server did not confirm uninstall. Refresh installed assets before retrying.",
        )
      toast.success("Asset uninstalled")
      setSelectedId(null)
      setUninstallTarget(null)
      await Promise.allSettled([mutate()])
    } catch (err) {
      setUninstallError(
        err instanceof Error
          ? err.message
          : "Uninstall failed. The install is retained for retry.",
      )
    } finally {
      lock.current = false
      setBusy(null)
    }
  }

  return (
    <AppShell title="Installed assets">
      <div
        className="bg-[color:var(--g-canvas)] pb-24 [&_[data-slot=button]]:min-h-11 [&_a]:min-h-11"
        data-composition="operate"
      >
        <GravitrePageHeader
          eyebrow="Operate / Installed capabilities"
          title="Installed assets"
          description="Marketplace assets your team has deployed, with quick links to agents, workflows, and knowledge sources."
          icon={<CheckCircle2 className="h-5 w-5" />}
          actions={
            <Button variant="outline" size="sm" asChild>
              <Link href="/marketplace/assets">
                <ArrowLeft className="mr-1.5 h-4 w-4" aria-hidden />
                Marketplace
              </Link>
            </Button>
          }
        />

        <div className="mx-auto w-full max-w-5xl space-y-6 px-[var(--np-page-pad-sm)] py-4 sm:px-[var(--np-page-pad)] sm:py-5">
          <section className="grid grid-cols-2 gap-[var(--np-kpi-gap)] sm:grid-cols-3">
            <GravitreMetric
              label="Active installs"
              value={data ? installed.length : "Not reported"}
              hint="Select an install — inspector stays closed until then."
              icon={<Package className="h-4 w-4" />}
            />
          </section>

          {error ? (
            <div role="alert">
              <GravitreSurface className="flex flex-col gap-3 border-destructive/30 bg-destructive/5 sm:flex-row sm:items-center sm:justify-between">
                <div className="space-y-1">
                  <p className="flex items-center gap-2 text-sm font-medium text-foreground">
                    <AlertTriangle
                      className="h-4 w-4 text-destructive"
                      aria-hidden
                    />
                    Could not load installed assets
                  </p>
                  <p className="text-sm text-muted-foreground">
                    {error instanceof Error
                      ? error.message
                      : "Check backend connectivity and try again."}
                  </p>
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => void mutate()}
                >
                  Retry
                </Button>
              </GravitreSurface>
            </div>
          ) : null}

          {isLoading && !data ? (
            <p className="text-sm text-muted-foreground">
              Loading installed assets…
            </p>
          ) : !data ? null : installed.length === 0 ? (
            <GravitreEmpty
              icon={<Package className="h-5 w-5" />}
              title="Nothing installed yet"
              hint="Install a department pack or catalog asset to deploy agents, workflows, and knowledge in one click."
              action={
                <Button asChild>
                  <Link href="/marketplace/assets?type=department_pack">
                    Browse department packs
                    <ArrowRight className="ml-1.5 h-4 w-4" aria-hidden />
                  </Link>
                </Button>
              }
            />
          ) : (
            <div className="flex min-w-0 overflow-hidden rounded-[10px] border border-divide bg-[color:var(--g-surface-1)] lg:flex-row">
              <ul
                className="min-w-0 flex-1 divide-y divide-divide"
                data-review-surface="marketplace-ops"
              >
                {installed.map((install) => (
                  <InstalledAssetRow
                    key={install.id}
                    install={install}
                    isSelected={selectedId === install.id}
                    onSelect={() =>
                      setSelectedId((current) =>
                        current === install.id ? null : install.id,
                      )
                    }
                  />
                ))}
              </ul>
              {selected && !useSheetInspector ? (
                <div className="min-w-0 flex-1 border-l border-divide bg-[color:var(--g-surface-1)]">
                  <Button
                    className="m-2"
                    variant="ghost"
                    onClick={() => setSelectedId(null)}
                  >
                    Close inspector
                  </Button>
                  <InstalledInspector
                    install={selected}
                    busy={busy}
                    onUninstall={(install) => {
                      setUninstallTarget(install)
                      setUninstallError(null)
                    }}
                    isAdmin={isAdmin}
                  />
                </div>
              ) : (
                <p className="sr-only">
                  Select an install — inspector stays closed until then.
                </p>
              )}
            </div>
          )}
        </div>
        {useSheetInspector ? (
          <Sheet
            open={Boolean(selected)}
            onOpenChange={(open) => {
              if (!open) setSelectedId(null)
            }}
          >
            <SheetContent className="w-full overflow-y-auto bg-[color:var(--g-canvas)] sm:max-w-lg">
              <SheetHeader>
                <SheetTitle className="font-[family-name:var(--font-space-grotesk)] text-2xl font-medium">
                  Installed capability
                </SheetTitle>
                <SheetDescription>
                  Inspect the pack and open its provisioned resources.
                </SheetDescription>
              </SheetHeader>
              {selected ? (
                <InstalledInspector
                  install={selected}
                  busy={busy}
                  onUninstall={(install) => {
                    setUninstallTarget(install)
                    setUninstallError(null)
                  }}
                  isAdmin={isAdmin}
                />
              ) : null}
            </SheetContent>
          </Sheet>
        ) : null}
      </div>
      <Dialog
        open={Boolean(uninstallTarget)}
        onOpenChange={(open) => {
          if (!open && !lock.current) setUninstallTarget(null)
        }}
      >
        <DialogContent className="[&_[data-slot=button]]:min-h-11">
          <DialogHeader>
            <DialogTitle>
              Uninstall {uninstallTarget?.asset?.title ?? "this asset"}?
            </DialogTitle>
            <DialogDescription>
              This removes the marketplace install record. Review the created
              resources separately before deleting any agents, workflows or
              knowledge.
            </DialogDescription>
          </DialogHeader>
          {uninstallError ? (
            <p role="alert" className="text-sm text-destructive">
              {uninstallError}
            </p>
          ) : null}
          <DialogFooter>
            <Button
              variant="outline"
              disabled={Boolean(busy)}
              onClick={() => setUninstallTarget(null)}
            >
              Keep installed
            </Button>
            <Button
              variant="destructive"
              disabled={Boolean(busy)}
              onClick={() =>
                uninstallTarget && void handleUninstall(uninstallTarget)
              }
            >
              {busy ? "Uninstalling…" : "Confirm uninstall"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </AppShell>
  )
}

export default function InstalledPage() {
  return <InstalledContent />
}
