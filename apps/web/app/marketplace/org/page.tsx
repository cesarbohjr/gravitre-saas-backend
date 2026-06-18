"use client"

import Link from "next/link"
import useSWR from "swr"
import { AppShell } from "@/components/gravitre/app-shell"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { marketplaceApi } from "@/lib/api"
import { useAuth } from "@/lib/auth-context"
import { ArrowLeft, ArrowRight, Building2, Loader2 } from "lucide-react"

export default function OrgMarketplacePage() {
  const { user } = useAuth()

  const { data, error, isLoading } = useSWR(user ? "marketplace-org-internal" : null, () =>
    marketplaceApi.listAssets({ visibility: "internal", limit: 100 }),
  )

  const assets = data?.assets ?? []

  return (
    <AppShell title="Your organization">
      <div className="mx-auto max-w-4xl space-y-6">
        <Button variant="ghost" size="sm" asChild className="-ml-2">
          <Link href="/marketplace">
            <ArrowLeft className="mr-1.5 h-4 w-4" aria-hidden />
            Marketplace
          </Link>
        </Button>

        <header>
          <h1 className="flex items-center gap-2 text-xl font-semibold">
            <Building2 className="h-5 w-5 text-primary" aria-hidden />
            Shared in your organization
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Internal assets published by your team — not visible in the public Gravitre catalog.
          </p>
        </header>

        {isLoading && !data ? (
          <div className="flex justify-center py-12">
            <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" aria-hidden />
          </div>
        ) : error ? (
          <div className="rounded-lg border border-destructive/30 bg-destructive/5 p-4 text-sm text-destructive">
            Could not load org assets.
          </div>
        ) : assets.length === 0 ? (
          <div className="rounded-xl border border-dashed p-10 text-center text-sm text-muted-foreground">
            No internal assets published yet. Org admins can approve drafts from the{" "}
            <Link href="/marketplace/org-admin" className="text-primary underline-offset-4 hover:underline">
              publish queue
            </Link>
            .
          </div>
        ) : (
          <div className="grid gap-4 sm:grid-cols-2">
            {assets.map((asset) => (
              <Link
                key={asset.id}
                href={`/marketplace/assets/${encodeURIComponent(asset.slug)}`}
                className="group rounded-xl border border-border bg-card p-4 transition-colors hover:border-primary/40"
              >
                <div className="mb-2 flex flex-wrap gap-2">
                  <Badge variant="outline">{asset.assetType.replace(/_/g, " ")}</Badge>
                  <Badge variant="secondary">internal</Badge>
                  {asset.installed ? <Badge>Installed</Badge> : null}
                </div>
                <h3 className="font-semibold text-foreground">{asset.title}</h3>
                {asset.description ? (
                  <p className="mt-1 line-clamp-2 text-sm text-muted-foreground">{asset.description}</p>
                ) : null}
                <span className="mt-3 inline-flex items-center text-sm font-medium text-primary">
                  View asset
                  <ArrowRight className="ml-1 h-4 w-4 transition-transform group-hover:translate-x-0.5" aria-hidden />
                </span>
              </Link>
            ))}
          </div>
        )}
      </div>
    </AppShell>
  )
}
