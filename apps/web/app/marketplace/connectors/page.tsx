"use client"

import { useEffect, useState } from "react"
import Link from "next/link"
import useSWR from "swr"
import { AppShell } from "@/components/gravitre/app-shell"
import {
  GravitreEmpty,
  GravitrePageHeader,
  GravitreSurface,
} from "@/components/gravitre/nodus-product"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Skeleton } from "@/components/ui/skeleton"
import { marketplaceApi } from "@/lib/api"
import { useAuth } from "@/lib/auth-context"
import { NucleoConnector } from "@/components/icons/nucleo/semantic"
import { ArrowLeft, Search } from "lucide-react"

function formatPrice(cents?: number, currency = "usd") {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: currency.toUpperCase(),
  }).format((cents ?? 0) / 100)
}

function useDebouncedValue(value: string, delayMs = 300): string {
  const [debounced, setDebounced] = useState(value)
  useEffect(() => {
    const timer = window.setTimeout(() => setDebounced(value), delayMs)
    return () => window.clearTimeout(timer)
  }, [value, delayMs])
  return debounced
}

export default function FederatedConnectorsPage() {
  const { user } = useAuth()
  const [search, setSearch] = useState("")
  const debouncedSearch = useDebouncedValue(search.trim())
  const { data, error, isLoading } = useSWR(
    user ? (["marketplace-federated-connectors", debouncedSearch] as const) : null,
    () =>
      marketplaceApi.listFederatedConnectors({
        search: debouncedSearch || undefined,
        limit: 100,
      }),
  )

  const assets = data?.assets ?? []

  return (
    <AppShell title="Partner connectors">
      <div className="bg-[color:var(--g-canvas)]">
        <GravitrePageHeader
          eyebrow="Gravitre Marketplace"
          title="Federated partner connectors"
          description="Partner registry entries surfaced in unified catalog shape. Linked entries also appear in the main catalog."
          icon={<NucleoConnector className="h-5 w-5" />}
          actions={
            <div className="flex flex-wrap gap-2">
              <Button variant="outline" size="sm" asChild>
                <Link href="/marketplace/assets">
                  <ArrowLeft className="mr-1.5 h-4 w-4" aria-hidden />
                  Marketplace home
                </Link>
              </Button>
              <Button variant="outline" size="sm" asChild>
                <Link href="/marketplace/assets?type=connector_config">Browse in catalog</Link>
              </Button>
            </div>
          }
        />

        <div className="mx-auto max-w-3xl space-y-6 px-[var(--np-page-pad-sm)] py-4 sm:px-[var(--np-page-pad)] sm:py-5">
          <div className="relative">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Search partner connectors…"
              className="rounded-[var(--np-radius-md)] pl-9"
            />
          </div>
          {isLoading && !data ? (
            <div className="space-y-3">
              {Array.from({ length: 4 }).map((_, index) => (
                <Skeleton key={index} className="h-20 rounded-[var(--np-radius-lg)]" />
              ))}
            </div>
          ) : error ? (
            <GravitreSurface className="border-destructive/30 bg-destructive/5 text-sm text-destructive">
              Could not load federated connectors.
            </GravitreSurface>
          ) : assets.length === 0 ? (
            <GravitreEmpty
              title={
                debouncedSearch
                  ? "No partner connectors match your search"
                  : "No published partner connectors yet"
              }
              hint={
                debouncedSearch
                  ? "Try a different search term."
                  : "Partner registry entries appear here when published."
              }
            />
          ) : (
            <ul className="space-y-3">
              {assets.map((asset) => (
                <li key={asset.registryId ?? asset.id}>
                  <GravitreSurface className="p-4 sm:p-4">
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div>
                        <div className="mb-1 flex flex-wrap gap-2">
                          <Badge variant="outline">partner registry</Badge>
                          {asset.verified ? <Badge>Certified</Badge> : null}
                          {asset.pricingType !== "free" ? (
                            <Badge variant="secondary">{formatPrice(asset.priceCents, asset.currency)}</Badge>
                          ) : (
                            <Badge variant="secondary">Free</Badge>
                          )}
                        </div>
                        <p className="font-medium text-foreground">{asset.title}</p>
                        {asset.description ? (
                          <p className="mt-1 text-sm text-muted-foreground">{asset.description}</p>
                        ) : null}
                        {asset.vendor ? (
                          <p className="mt-1 text-xs text-muted-foreground">Vendor: {asset.vendor}</p>
                        ) : null}
                      </div>
                      <div className="flex flex-wrap gap-2">
                        {asset.slug ? (
                          <Button variant="default" size="sm" asChild>
                            <Link href={`/marketplace/assets/${encodeURIComponent(asset.slug)}`}>Catalog detail</Link>
                          </Button>
                        ) : null}
                        <Button variant="outline" size="sm" asChild>
                          <Link href="/marketplace/submit">Partner track</Link>
                        </Button>
                      </div>
                    </div>
                  </GravitreSurface>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </AppShell>
  )
}
