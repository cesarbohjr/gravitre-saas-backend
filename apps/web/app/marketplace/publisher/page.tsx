"use client"

import { useState } from "react"
import Link from "next/link"
import useSWR from "swr"
import { AppShell } from "@/components/gravitre/app-shell"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { marketplaceApi } from "@/lib/api"
import { useAuth } from "@/lib/auth-context"
import { ArrowLeft, CheckCircle2, Loader2, Sparkles } from "lucide-react"
import { toast } from "sonner"

export default function MarketplacePublisherPage() {
  const { user } = useAuth()
  const role = (user as { role?: string } | null)?.role
  const isAdmin = role === "admin" || role === "owner"
  const [displayName, setDisplayName] = useState("")
  const [slug, setSlug] = useState("")
  const [description, setDescription] = useState("")
  const [websiteUrl, setWebsiteUrl] = useState("")
  const [busy, setBusy] = useState(false)

  const { data, mutate, isLoading } = useSWR(
    user && isAdmin ? "marketplace-publisher-profile" : null,
    () => marketplaceApi.getPublisherProfile(),
  )

  const publisher = data?.publisher

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
      toast.success("Publisher profile ready for public submissions")
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

  return (
    <AppShell title="Become a publisher">
      <div className="mx-auto max-w-xl space-y-6">
        <Button variant="ghost" size="sm" asChild className="-ml-2">
          <Link href="/marketplace">
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
            Set up your organization profile to submit assets to the public Gravitre catalog.
          </p>
        </header>

        {publisher?.publicPublishingEnabled ? (
          <div className="rounded-xl border border-success/30 bg-success/5 p-5">
            <div className="flex items-center gap-2">
              <CheckCircle2 className="h-5 w-5 text-success" aria-hidden />
              <h2 className="font-semibold">{publisher.displayName}</h2>
              {publisher.verified ? <Badge>Verified publisher</Badge> : null}
            </div>
            <p className="mt-2 text-sm text-muted-foreground">{publisher.description}</p>
            <p className="mt-3 text-xs text-muted-foreground">Publisher slug: {publisher.slug}</p>
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
                placeholder={publisher?.displayName ?? "Acme AI Studio"}
                required
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium" htmlFor="slug">
                Publisher slug (optional)
              </label>
              <Input
                id="slug"
                value={slug}
                onChange={(event) => setSlug(event.target.value)}
                placeholder={publisher?.slug ?? "acme-ai-studio"}
              />
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
              {publisher?.publicPublishingEnabled ? "Update publisher profile" : "Complete onboarding"}
            </Button>
          </form>
        )}
      </div>
    </AppShell>
  )
}
