"use client"

import { useEffect, useState } from "react"
import Link from "next/link"
import useSWR from "swr"
import { AppShell } from "@/components/gravitre/app-shell"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { marketplaceApi } from "@/lib/api"
import { useAuth } from "@/lib/auth-context"
import { useOrgAdmin } from "@/lib/use-org-admin"
import {
  ArrowLeft,
  ArrowRight,
  CheckCircle2,
  DollarSign,
  ExternalLink,
  Loader2,
  Sparkles,
} from "lucide-react"
import { toast } from "sonner"

export default function MarketplacePublisherPage() {
  const { user } = useAuth()
  const { isAdmin } = useOrgAdmin()
  const [displayName, setDisplayName] = useState("")
  const [slug, setSlug] = useState("")
  const [description, setDescription] = useState("")
  const [websiteUrl, setWebsiteUrl] = useState("")
  const [busy, setBusy] = useState(false)
  const [hydrated, setHydrated] = useState(false)

  const { data, mutate, isLoading } = useSWR(
    user && isAdmin ? "marketplace-publisher-profile" : null,
    () => marketplaceApi.getPublisherProfile(),
  )

  const onboarded = Boolean(data?.publisher?.publicPublishingEnabled)

  const { data: billing } = useSWR(
    user && isAdmin && onboarded ? "marketplace-publisher-billing" : null,
    () => marketplaceApi.billingStatus(),
  )

  const publisher = data?.publisher
  const assetPayouts = billing?.assetPayouts
  const connectReady =
    billing?.account?.connectStatus === "active" &&
    billing.account.chargesEnabled &&
    billing.account.payoutsEnabled
  const creatorSharePct =
    billing?.platformFeeBps != null ? 100 - billing.platformFeeBps / 100 : 80

  useEffect(() => {
    if (!publisher || hydrated) return
    setDisplayName(publisher.displayName ?? "")
    setSlug(publisher.slug ?? "")
    setDescription(publisher.description ?? "")
    setWebsiteUrl(publisher.websiteUrl ?? "")
    setHydrated(true)
  }, [publisher, hydrated])

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault()
    if (!displayName.trim()) {
      toast.error("Display name is required")
      return
    }
    setBusy(true)
    try {
      await marketplaceApi.onboardPublisher({
        displayName: displayName.trim(),
        slug: slug.trim() || undefined,
        description: description.trim() || undefined,
        websiteUrl: websiteUrl.trim() || undefined,
      })
      toast.success(
        publisher?.publicPublishingEnabled
          ? "Publisher profile updated"
          : "Publisher onboarding complete — you can submit public assets",
      )
      setHydrated(false)
      await mutate()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Onboarding failed")
    } finally {
      setBusy(false)
    }
  }

  if (!isAdmin) {
    return (
      <AppShell title="Become a publisher">
        <div className="mx-auto max-w-lg rounded-lg border bg-card p-6 text-center text-sm text-muted-foreground">
          Admin access is required to set up your organization as a marketplace publisher.
        </div>
      </AppShell>
    )
  }

  function formatUsd(cents: number) {
    return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(cents / 100)
  }

  return (
    <AppShell title="Become a publisher">
      <div className="mx-auto max-w-xl space-y-6">
        <Button variant="ghost" size="sm" asChild className="-ml-2">
          <Link href="/marketplace/assets">
            <ArrowLeft className="mr-1.5 h-4 w-4" aria-hidden />
            Marketplace
          </Link>
        </Button>

        <header>
          <h1 className="flex items-center gap-2 text-xl font-semibold">
            <Sparkles className="h-5 w-5 text-primary" aria-hidden />
            Creator publisher onboarding
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Register your organization as a creator on the public Gravitre catalog. Internal org
            publishing does not require this step.
          </p>
        </header>

        {onboarded ? (
          <div className="rounded-xl border border-success/30 bg-success/5 p-5 space-y-3">
            <div className="flex flex-wrap items-center gap-2">
              <CheckCircle2 className="h-5 w-5 text-success" aria-hidden />
              <h2 className="font-semibold">{publisher?.displayName}</h2>
              <Badge variant="secondary">Public publishing enabled</Badge>
              {publisher?.verified ? <Badge>Verified publisher</Badge> : null}
            </div>
            {publisher?.description ? (
              <p className="text-sm text-muted-foreground">{publisher.description}</p>
            ) : null}
            <dl className="grid gap-2 text-xs text-muted-foreground sm:grid-cols-2">
              <div>
                <dt className="font-medium text-foreground/80">Publisher slug</dt>
                <dd>{publisher?.slug}</dd>
              </div>
              {publisher?.websiteUrl ? (
                <div>
                  <dt className="font-medium text-foreground/80">Website</dt>
                  <dd>
                    <a
                      href={publisher.websiteUrl}
                      target="_blank"
                      rel="noreferrer"
                      className="inline-flex items-center gap-1 text-primary hover:underline"
                    >
                      {publisher.websiteUrl.replace(/^https?:\/\//, "")}
                      <ExternalLink className="h-3 w-3" aria-hidden />
                    </a>
                  </dd>
                </div>
              ) : null}
            </dl>
            <div className="flex flex-wrap gap-2 pt-1">
              <Button size="sm" asChild>
                <Link href="/marketplace/org/assets/new">
                  Create draft asset
                  <ArrowRight className="ml-1.5 h-3.5 w-3.5" aria-hidden />
                </Link>
              </Button>
              <Button size="sm" variant="outline" asChild>
                <Link href="/marketplace/org-admin">Org publish admin</Link>
              </Button>
            </div>
          </div>
        ) : (
          <div className="rounded-xl border border-dashed p-5 text-sm text-muted-foreground">
            <p className="font-medium text-foreground">What you unlock</p>
            <ul className="mt-2 list-inside list-disc space-y-1">
              <li>Submit org-owned drafts to the public Gravitre review queue</li>
              <li>Publisher profile shown on your public catalog assets</li>
              <li>{creatorSharePct}% creator revenue share on paid asset sales after Stripe Connect</li>
            </ul>
          </div>
        )}

        {onboarded ? (
          <div className="rounded-xl border bg-card p-5 space-y-4">
            <div className="flex items-start gap-2">
              <DollarSign className="mt-0.5 h-5 w-5 text-primary" aria-hidden />
              <div>
                <h2 className="font-semibold">Paid asset revenue share</h2>
                <p className="mt-1 text-sm text-muted-foreground">
                  You receive {creatorSharePct}% of each paid install after the platform fee. Connect
                  Stripe to receive automatic transfers when buyers purchase your public assets.
                </p>
              </div>
            </div>
            {assetPayouts && assetPayouts.payoutCount > 0 ? (
              <dl className="grid gap-3 text-sm sm:grid-cols-3">
                <div>
                  <dt className="text-xs text-muted-foreground">Asset sales</dt>
                  <dd className="font-semibold tabular-nums">{formatUsd(assetPayouts.grossCents)}</dd>
                </div>
                <div>
                  <dt className="text-xs text-muted-foreground">Your earnings</dt>
                  <dd className="font-semibold tabular-nums">
                    {formatUsd(assetPayouts.partnerEarningsCents)}
                  </dd>
                </div>
                <div>
                  <dt className="text-xs text-muted-foreground">Pending transfer</dt>
                  <dd className="font-semibold tabular-nums">
                    {formatUsd(assetPayouts.pendingTransferCents)}
                  </dd>
                </div>
              </dl>
            ) : (
              <p className="text-sm text-muted-foreground">
                No paid sales yet. Set pricing on public assets after they are approved.
              </p>
            )}
            <div className="flex flex-wrap gap-2">
              <Button size="sm" variant={connectReady ? "outline" : "default"} asChild>
                <Link href="/marketplace/billing">
                  {connectReady ? "Manage payouts" : "Connect Stripe payouts"}
                </Link>
              </Button>
              <Button size="sm" variant="outline" asChild>
                <Link href="/marketplace/publisher/analytics">Revenue analytics</Link>
              </Button>
            </div>
          </div>
        ) : null}

        {isLoading && !data ? (
          <div className="h-40 animate-pulse rounded-xl border bg-muted/40" />
        ) : (
          <form onSubmit={handleSubmit} className="space-y-4 rounded-xl border bg-card p-5">
            <div className="space-y-2">
              <label className="text-sm font-medium" htmlFor="displayName">
                Display name
              </label>
              <Input
                id="displayName"
                value={displayName}
                onChange={(event) => setDisplayName(event.target.value)}
                placeholder="Acme AI Studio"
                required
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium" htmlFor="slug">
                Publisher slug
              </label>
              <Input
                id="slug"
                value={slug}
                onChange={(event) => setSlug(event.target.value)}
                placeholder="acme-ai-studio"
              />
              <p className="text-xs text-muted-foreground">Lowercase letters, numbers, and hyphens.</p>
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium" htmlFor="description">
                About your team
              </label>
              <Textarea
                id="description"
                value={description}
                onChange={(event) => setDescription(event.target.value)}
                placeholder="What kinds of agents, workflows, or packs do you publish?"
                rows={4}
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium" htmlFor="websiteUrl">
                Website (optional)
              </label>
              <Input
                id="websiteUrl"
                value={websiteUrl}
                onChange={(event) => setWebsiteUrl(event.target.value)}
                placeholder="https://example.com"
              />
            </div>
            <Button type="submit" disabled={busy}>
              {busy ? <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden /> : null}
              {onboarded ? "Update publisher profile" : "Complete onboarding"}
            </Button>
          </form>
        )}
      </div>
    </AppShell>
  )
}
