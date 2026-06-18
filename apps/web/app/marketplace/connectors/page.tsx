"use client"

import Link from "next/link"
import useSWR from "swr"
import { AppShell } from "@/components/gravitre/app-shell"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { marketplaceApi } from "@/lib/api"
import { useAuth } from "@/lib/auth-context"
import { ArrowLeft, Plug } from "lucide-react"

function formatPrice(cents?: number, currency = "usd") {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: currency.toUpperCase(),
  }).format((cents ?? 0) / 100)
}

export default function FederatedConnectorsPage() {
  const { user } = useAuth()
  const { data, error, isLoading } = useSWR(
    user ? "marketplace-federated-connectors" : null,
    () => marketplaceApi.listFederatedConnectors({ limit: 100 }),
  )

  return (
    <AppShell title="Partner connectors">
      <div className="mx-auto max-w-3xl space-y-6">
        <Button variant="ghost" size="sm" asChild className="-ml-2">
          <Link href="/marketplace">
            <ArrowLeft className="mr-1.5 h-4 w-4" aria-hidden />
            Marketplace home
          </Link>
        </Button>
        <div>
          <h1 className="flex items-center gap-2 text-xl font-semibold text-foreground">
            <Plug className="h-5 w-5 text-primary" aria-hidden />
            Federated partner connectors
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Partner registry entries surfaced in unified catalog shape. Install via the partner connector track.
          </p>
        </div>
        {isLoading && !data ? (
          <div className="space-y-3">
            {Array.from({ length: 4 }).map((_, index) => (
              <Skeleton key={index} className="h-20 rounded-xl" />
            ))}
          </div>
        ) : error ? (
          <div className="rounded-lg border border-destructive/30 bg-destructive/5 p-4 text-sm text-destructive">
            Could not load federated connectors.
          </div>
        ) : (
          <ul className="space-y-3">
            {(data?.assets ?? []).map((asset) => (
              <li key={asset.registryId ?? asset.id} className="rounded-xl border bg-card p-4">
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
                  <Button variant="outline" size="sm" asChild>
                    <Link href="/marketplace/submit">Partner track</Link>
                  </Button>
                </div>
              </li>
            ))}
            {!data?.assets?.length ? (
              <li className="rounded-lg border border-dashed p-6 text-center text-sm text-muted-foreground">
                No published partner connectors yet.
              </li>
            ) : null}
          </ul>
        )}
      </div>
    </AppShell>
  )
}
