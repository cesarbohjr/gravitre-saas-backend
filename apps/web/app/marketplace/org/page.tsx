"use client"

import Link from "next/link"
import useSWR from "swr"
import { AppShell } from "@/components/gravitre/app-shell"
import {
  GravitreEmpty,
  GravitreMetric,
  GravitrePageHeader,
  GravitreSurface,
} from "@/components/gravitre/nodus-product"
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
      <div className="bg-[color:var(--g-canvas)]">
        <GravitrePageHeader
          eyebrow="Gravitre Marketplace"
          title="Shared in your organization"
          description="Internal assets published by your team — not visible in the public Gravitre catalog."
          icon={<Building2 className="h-5 w-5" />}
          actions={
            <Button variant="outline" size="sm" asChild>
              <Link href="/marketplace/assets">
                <ArrowLeft className="mr-1.5 h-4 w-4" aria-hidden />
                Marketplace
              </Link>
            </Button>
          }
        />

        <div className="mx-auto max-w-4xl space-y-6 px-[var(--np-page-pad-sm)] py-4 sm:px-[var(--np-page-pad)] sm:py-5">
          <section className="grid grid-cols-2 gap-[var(--np-kpi-gap)] sm:grid-cols-3">
            <GravitreMetric
              label="Internal assets"
              value={isLoading && !data ? "—" : assets.length}
              hint="Org visibility"
              icon={<Building2 className="h-4 w-4" />}
            />
          </section>

          {isLoading && !data ? (
            <div className="flex justify-center py-12">
              <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" aria-hidden />
            </div>
          ) : error ? (
            <GravitreSurface className="border-destructive/30 bg-destructive/5 text-sm text-destructive">
              Could not load org assets.
            </GravitreSurface>
          ) : assets.length === 0 ? (
            <GravitreEmpty
              title="No internal assets published yet"
              hint="Org admins can approve drafts from the publish queue."
              action={
                <Button variant="outline" size="sm" asChild>
                  <Link href="/marketplace/org-admin">Open publish queue</Link>
                </Button>
              }
            />
          ) : (
            <div className="grid gap-4 sm:grid-cols-2">
              {assets.map((asset) => (
                <Link key={asset.id} href={`/marketplace/assets/${encodeURIComponent(asset.slug)}`}>
                  <GravitreSurface className="group h-full transition-colors hover:border-[color:var(--g-brand-border)]">
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
                  </GravitreSurface>
                </Link>
              ))}
            </div>
          )}
        </div>
      </div>
    </AppShell>
  )
}
