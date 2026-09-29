"use client"

import { useState } from "react"
import Link from "next/link"
import useSWR from "swr"
import { AppShell } from "@/components/gravitre/app-shell"
import {
  GravitreEmpty,
  GravitreMetric,
  GravitrePageHeader,
  GravitreSurface,
} from "@/components/gravitre/nodus-product"
import { Button } from "@/components/ui/button"
import { marketplaceApi } from "@/lib/api"
import { DepartmentPipelineByDepartment } from "@/components/marketplace/department-pipeline-panel"
import { useAuth } from "@/lib/auth-context"
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
  return date.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" })
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
  const department = asset?.department ?? "general"
  const installedAt = formatInstalledAt(install.installedAt)
  return (
    <li>
      <button
        type="button"
        onClick={onSelect}
        className={cn(
          "flex w-full items-start justify-between gap-3 px-3 py-2.5 text-left",
          isSelected ? "bg-[color:var(--g-surface-2)]" : "hover:bg-[color:var(--g-surface-2)]/50",
        )}
      >
        <span className="min-w-0">
          <span className="block text-sm font-medium text-foreground">{asset?.title ?? "Installed asset"}</span>
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
}: {
  install: MarketplaceInstall
  busy: string | null
  onUninstall: (install: MarketplaceInstall) => void
}) {
  const asset = install.asset
  const department = asset?.department ?? "general"
  const installedAt = formatInstalledAt(install.installedAt)
  const slug = asset?.slug
  const agentCount =
    install.metadata?.agentIds?.length ??
    (install.metadata?.agentId || install.metadata?.operatorId ? 1 : 0)
  const workflowCount =
    install.metadata?.workflowIds?.length ?? (install.metadata?.workflowId ? 1 : 0)
  const sourceCount =
    install.metadata?.ragSourceIds?.length ?? (install.metadata?.ragSourceId ? 1 : 0)
  const deepLinks = (install.deepLinks ?? []).filter(
    (link) => !(link.label === "Primary" && (install.deepLinks?.length ?? 0) > 1),
  )

  return (
    <div className="space-y-4 p-4" data-review-surface="marketplace-ops-inspect">
      <div>
        <p className="text-xs font-medium text-muted-foreground">Install</p>
        <h2 className="mt-1 text-base font-medium text-foreground">{asset?.title ?? "Installed asset"}</h2>
        <p className="mt-1 text-xs capitalize text-muted-foreground">
          {department.replace(/-/g, " ")}
          {installedAt ? ` · Installed ${installedAt}` : ""}
        </p>
      </div>
      {deepLinks.length ? (
        <ul className="divide-y divide-divide border-y border-divide text-sm">
          {deepLinks.slice(0, 4).map((link) => (
            <li key={`${link.entityType}:${link.entityId}:${link.path}`}>
              <Link
                href={link.entityType === "workflow" ? `${link.path}/builder` : link.path}
                className="flex items-center justify-between py-2 hover:underline"
              >
                {link.label}
                <ArrowRight className="h-3.5 w-3.5 text-muted-foreground" aria-hidden />
              </Link>
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-sm text-muted-foreground">
          {agentCount} agents · {workflowCount} workflows · {sourceCount} sources
        </p>
      )}
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
  )
}

function InstalledContent() {
  const { user } = useAuth()
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
    if (!slug) return
    if (!window.confirm(`Uninstall "${install.asset?.title ?? slug}"? This removes the marketplace install record.`)) {
      return
    }
    setBusy(install.id)
    try {
      await marketplaceApi.uninstallAsset(slug)
      toast.success("Asset uninstalled")
      setSelectedId(null)
      await mutate()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Uninstall failed")
    } finally {
      setBusy(null)
    }
  }

  return (
    <AppShell title="Installed assets">
      <div className="bg-[color:var(--g-canvas)]">
        <GravitrePageHeader
          eyebrow="Gravitre Marketplace"
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
              value={isLoading && !data ? "—" : installed.length}
              hint="Select an install — inspector stays closed until then."
              icon={<Package className="h-4 w-4" />}
            />
          </section>

          {error ? (
            <div role="alert">
              <GravitreSurface className="flex flex-col gap-3 border-destructive/30 bg-destructive/5 sm:flex-row sm:items-center sm:justify-between">
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
              </GravitreSurface>
            </div>
          ) : null}

          {isLoading && !data ? (
            <p className="text-sm text-muted-foreground">Loading installed assets…</p>
          ) : installed.length === 0 ? (
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
            <div className="flex flex-col border border-divide lg:flex-row">
              <ul className="min-w-0 flex-1 divide-y divide-divide" data-review-surface="marketplace-ops">
                {installed.map((install) => (
                  <InstalledAssetRow
                    key={install.id}
                    install={install}
                    isSelected={selectedId === install.id}
                    onSelect={() => setSelectedId(install.id)}
                  />
                ))}
              </ul>
              {selected ? (
                <div className="flex-1 border-t border-divide bg-[color:var(--g-canvas)] lg:border-t-0 lg:border-l">
                  <InstalledInspector install={selected} busy={busy} onUninstall={handleUninstall} />
                </div>
              ) : (
                <p className="sr-only">Select an install — inspector stays closed until then.</p>
              )}
            </div>
          )}
        </div>
      </div>
    </AppShell>
  )
}

export default function InstalledPage() {
  return <InstalledContent />
}
