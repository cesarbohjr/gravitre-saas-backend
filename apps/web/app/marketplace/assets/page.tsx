"use client"

import { Suspense, useMemo, useState } from "react"
import Link from "next/link"
import useSWR from "swr"
import { AppShell } from "@/components/gravitre/app-shell"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { GridPattern } from "@/components/gravitre/premium-effects"
import { marketplaceApi } from "@/lib/api"
import { useAuth } from "@/lib/auth-context"
import { cn } from "@/lib/utils"
import {
  Bot,
  CheckCircle2,
  Copy,
  Database,
  Loader2,
  Package,
  Plug,
  Search,
  Sparkles,
  Workflow,
} from "lucide-react"
import { toast } from "sonner"
import type { MarketplaceAssetSummary, MarketplaceConnectorChecklistItem } from "@/types/api"

const TYPE_FILTERS = [
  { id: "all", label: "All" },
  { id: "ai_agent", label: "Agents", icon: Bot },
  { id: "workflow", label: "Workflows", icon: Workflow },
  { id: "knowledge_pack", label: "Knowledge", icon: Database },
  { id: "department_pack", label: "Department packs", icon: Package },
] as const

const TYPE_ICONS: Record<string, typeof Bot> = {
  ai_agent: Bot,
  workflow: Workflow,
  knowledge_pack: Database,
  department_pack: Package,
}

function ConnectorChecklist({ items }: { items: MarketplaceConnectorChecklistItem[] }) {
  if (!items.length) return null
  return (
    <ul className="space-y-2">
      {items.map((item) => (
        <li key={item.connectorType} className="flex items-start justify-between gap-2 text-sm">
          <div className="flex items-center gap-2">
            {item.connected ? (
              <CheckCircle2 className="h-4 w-4 shrink-0 text-success" aria-hidden />
            ) : (
              <Plug className="h-4 w-4 shrink-0 text-muted-foreground" aria-hidden />
            )}
            <span className={cn(!item.connected && item.required && "text-foreground")}>
              {item.label || item.connectorType}
              {item.required ? "" : " (optional)"}
            </span>
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

function AssetCard({
  asset,
  isAdmin,
  busy,
  onInstall,
  onClone,
}: {
  asset: MarketplaceAssetSummary
  isAdmin: boolean
  busy: string | null
  onInstall: (asset: MarketplaceAssetSummary) => void
  onClone: (asset: MarketplaceAssetSummary) => void
}) {
  const Icon = TYPE_ICONS[asset.assetType] ?? Sparkles
  const ready = asset.connectorsReady || asset.requiredConnectorsTotal === 0
  const blocked = !ready && !asset.installed

  return (
    <article
      className={cn(
        "flex h-full flex-col rounded-xl border bg-card p-5 shadow-sm transition-shadow hover:shadow-md",
        asset.installed ? "border-success/30" : "border-border",
      )}
    >
      <div className="mb-3 flex items-start justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="grid h-10 w-10 place-items-center rounded-lg bg-primary/10 text-primary">
            <Icon className="h-5 w-5" aria-hidden />
          </div>
          <div>
            <h3 className="font-semibold leading-tight">{asset.title}</h3>
            <p className="text-xs text-muted-foreground">{asset.department ?? asset.assetType}</p>
          </div>
        </div>
        {asset.installed ? <Badge variant="secondary">Installed</Badge> : null}
      </div>

      {asset.description ? (
        <p className="mb-4 line-clamp-3 flex-1 text-sm text-muted-foreground">{asset.description}</p>
      ) : (
        <div className="flex-1" />
      )}

      <div className="mb-4 flex flex-wrap gap-1.5">
        {(asset.tags ?? []).slice(0, 4).map((tag) => (
          <Badge key={tag} variant="outline" className="text-[10px]">
            {tag}
          </Badge>
        ))}
      </div>

      {asset.connectorChecklist?.length ? (
        <div className="mb-4 rounded-lg border border-border/60 bg-muted/20 p-3">
          <p className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
            Connector checklist ({asset.requiredConnectorsConnected}/{asset.requiredConnectorsTotal})
          </p>
          <ConnectorChecklist items={asset.connectorChecklist} />
        </div>
      ) : null}

      <div className="mt-auto flex flex-wrap gap-2">
        {isAdmin && !asset.installed ? (
          <Button
            size="sm"
            disabled={Boolean(busy) || blocked}
            onClick={() => onInstall(asset)}
          >
            {busy === asset.id ? (
              <>
                <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" aria-hidden />
                Installing…
              </>
            ) : blocked ? (
              "Connect apps first"
            ) : (
              "Install"
            )}
          </Button>
        ) : null}
        <Button
          size="sm"
          variant="secondary"
          disabled={Boolean(busy)}
          onClick={() => onClone(asset)}
        >
          {busy === `clone:${asset.id}` ? (
            <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" aria-hidden />
          ) : (
            <Copy className="mr-1.5 h-3.5 w-3.5" aria-hidden />
          )}
          Clone
        </Button>
      </div>
    </article>
  )
}

function MarketplaceAssetsContent() {
  const { user } = useAuth()
  const role = user?.role
  const isAdmin = role === "admin" || role === "owner"
  const [typeFilter, setTypeFilter] = useState<string>("all")
  const [search, setSearch] = useState("")
  const [busy, setBusy] = useState<string | null>(null)

  const swrKey = user
    ? ["marketplace-assets", typeFilter, search] as const
    : null

  const { data, error, isLoading, mutate } = useSWR(swrKey, () =>
    marketplaceApi.listAssets({
      assetType: typeFilter === "all" ? undefined : typeFilter,
      search: search.trim() || undefined,
      limit: 100,
    }),
  )

  const assets = data?.assets ?? []

  const handleInstall = async (asset: MarketplaceAssetSummary) => {
    setBusy(asset.id)
    try {
      const result = await marketplaceApi.installAsset(asset.slug)
      toast.success(`${asset.title} installed`, {
        description: "Agents, workflows, and knowledge sources were provisioned for your org.",
      })
      if (result.entities?.workflowId) {
        toast.message("Open workflow", {
          action: {
            label: "View",
            onClick: () => {
              window.location.href = `/workflows/${String(result.entities?.workflowId)}/builder`
            },
          },
        })
      }
      await mutate()
    } catch (err) {
      const message = err instanceof Error ? err.message : "Install failed"
      toast.error(/connect required apps/i.test(message) ? "Connect required apps first" : "Install failed", {
        description: message,
      })
    } finally {
      setBusy(null)
    }
  }

  const handleClone = async (asset: MarketplaceAssetSummary) => {
    setBusy(`clone:${asset.id}`)
    try {
      const result = await marketplaceApi.cloneAsset(asset.slug)
      toast.success("Private copy created", {
        description: `${result.asset.title} is saved as a draft in your org.`,
      })
    } catch (err) {
      toast.error("Clone failed", {
        description: err instanceof Error ? err.message : "Try again",
      })
    } finally {
      setBusy(null)
    }
  }

  const emptyMessage = useMemo(() => {
    if (search.trim()) return "No assets match your search."
    if (typeFilter !== "all") return "No assets in this category yet."
    return "The starter catalog is empty. Run the marketplace seed script."
  }, [search, typeFilter])

  return (
    <AppShell
      title="Marketplace"
      description="Browse Gravitre starter agents, workflows, knowledge packs, and department bundles."
    >
      <div className="relative overflow-hidden rounded-2xl border bg-card/40 p-6 md:p-8">
        <GridPattern className="opacity-40" />
        <div className="relative space-y-6">
          <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Link href="/marketplace/submit" className="hover:text-foreground">
                Partner submissions
              </Link>
              <span aria-hidden>·</span>
              <Link href="/connectors" className="hover:text-foreground">
                Connectors
              </Link>
            </div>
            <div className="relative w-full md:max-w-sm">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                placeholder="Search marketplace…"
                className="pl-9"
              />
            </div>
          </div>

          <div className="flex flex-wrap gap-2">
            {TYPE_FILTERS.map((filter) => (
              <Button
                key={filter.id}
                size="sm"
                variant={typeFilter === filter.id ? "default" : "outline"}
                onClick={() => setTypeFilter(filter.id)}
              >
                {filter.label}
              </Button>
            ))}
          </div>

          {isLoading ? (
            <div className="grid place-items-center py-20 text-muted-foreground">
              <Loader2 className="h-8 w-8 animate-spin" aria-hidden />
            </div>
          ) : error ? (
            <div className="rounded-lg border border-destructive/40 bg-destructive/5 p-4 text-sm text-destructive">
              Failed to load marketplace catalog.
            </div>
          ) : assets.length === 0 ? (
            <div className="rounded-lg border border-dashed p-10 text-center text-sm text-muted-foreground">
              {emptyMessage}
            </div>
          ) : (
            <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
              {assets.map((asset) => (
                <AssetCard
                  key={asset.id}
                  asset={asset}
                  isAdmin={isAdmin}
                  busy={busy}
                  onInstall={handleInstall}
                  onClone={handleClone}
                />
              ))}
            </div>
          )}
        </div>
      </div>
    </AppShell>
  )
}

export default function MarketplaceAssetsPage() {
  return (
    <Suspense
      fallback={
        <div className="grid min-h-[40vh] place-items-center text-muted-foreground">
          <Loader2 className="h-8 w-8 animate-spin" aria-hidden />
        </div>
      }
    >
      <MarketplaceAssetsContent />
    </Suspense>
  )
}
