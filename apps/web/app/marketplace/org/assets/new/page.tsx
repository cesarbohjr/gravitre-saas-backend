"use client"

import { useState } from "react"
import Link from "next/link"
import { useRouter } from "next/navigation"
import { AppShell } from "@/components/gravitre/app-shell"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { marketplaceApi } from "@/lib/api"
import { useAuth } from "@/lib/auth-context"
import { ArrowLeft, Loader2, PlusCircle } from "lucide-react"
import { toast } from "sonner"

function slugify(value: string): string {
  return value
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
}

export default function CreateOrgAssetPage() {
  const router = useRouter()
  const { user } = useAuth()
  const role = user?.role
  const isAdmin = role === "admin" || role === "owner"
  const [busy, setBusy] = useState(false)
  const [title, setTitle] = useState("")
  const [slug, setSlug] = useState("")
  const [slugTouched, setSlugTouched] = useState(false)
  const [description, setDescription] = useState("")
  const [purpose, setPurpose] = useState("")
  const [roleName, setRoleName] = useState("")
  const [department, setDepartment] = useState("")
  const [businessOutcome, setBusinessOutcome] = useState("")
  const [useCase, setUseCase] = useState("")
  const [estimatedHours, setEstimatedHours] = useState("")

  const handleTitleChange = (value: string) => {
    setTitle(value)
    if (!slugTouched) {
      setSlug(slugify(value))
    }
  }

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault()
    const normalizedSlug = slugify(slug || title)
    if (!title.trim() || !normalizedSlug) {
      toast.error("Title and slug are required")
      return
    }
    setBusy(true)
    try {
      const parsedHours = estimatedHours.trim() ? Number(estimatedHours) : undefined
      const result = await marketplaceApi.createOrgAsset({
        slug: normalizedSlug,
        title: title.trim(),
        description: description.trim() || undefined,
        assetType: "ai_agent",
        department: department.trim() || undefined,
        businessOutcome: businessOutcome.trim() || undefined,
        useCase: useCase.trim() || undefined,
        estimatedHoursSaved:
          parsedHours != null && !Number.isNaN(parsedHours) ? parsedHours : undefined,
        config: {
          name: title.trim(),
          purpose: purpose.trim(),
          role: roleName.trim(),
          department: department.trim(),
          systems: [],
        },
      })
      toast.success("Draft asset created")
      router.push(`/marketplace/org-admin?created=${encodeURIComponent(result.asset.slug)}`)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not create asset")
    } finally {
      setBusy(false)
    }
  }

  if (!isAdmin) {
    return (
      <AppShell title="Create org asset">
        <div className="mx-auto max-w-lg rounded-lg border bg-card p-6 text-center text-sm text-muted-foreground">
          Admin access is required to create org marketplace assets.
        </div>
      </AppShell>
    )
  }

  return (
    <AppShell title="Create org asset">
      <div className="mx-auto max-w-xl space-y-6">
        <Button variant="ghost" size="sm" asChild className="-ml-2">
          <Link href="/marketplace/org-admin">
            <ArrowLeft className="mr-1.5 h-4 w-4" aria-hidden />
            Org admin
          </Link>
        </Button>

        <header>
          <h1 className="flex items-center gap-2 text-xl font-semibold">
            <PlusCircle className="h-5 w-5 text-primary" aria-hidden />
            Create internal asset
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Save a draft AI agent for your organization. Submit it for review when ready to publish internally.
          </p>
        </header>

        <form onSubmit={handleSubmit} className="space-y-4 rounded-xl border bg-card p-5">
          <div className="space-y-2">
            <label className="text-sm font-medium" htmlFor="title">
              Title
            </label>
            <Input
              id="title"
              value={title}
              onChange={(event) => handleTitleChange(event.target.value)}
              placeholder="Campaign analyst agent"
              required
            />
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium" htmlFor="slug">
              Slug
            </label>
            <Input
              id="slug"
              value={slug}
              onChange={(event) => {
                setSlugTouched(true)
                setSlug(event.target.value)
              }}
              placeholder="campaign-analyst-agent"
              required
            />
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium" htmlFor="description">
              Description
            </label>
            <Textarea
              id="description"
              value={description}
              onChange={(event) => setDescription(event.target.value)}
              placeholder="What does this asset help your team do?"
              rows={3}
            />
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <label className="text-sm font-medium" htmlFor="roleName">
                Role
              </label>
              <Input
                id="roleName"
                value={roleName}
                onChange={(event) => setRoleName(event.target.value)}
                placeholder="Marketing analyst"
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium" htmlFor="department">
                Department
              </label>
              <Input
                id="department"
                value={department}
                onChange={(event) => setDepartment(event.target.value)}
                placeholder="Marketing"
              />
            </div>
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium" htmlFor="purpose">
              Purpose
            </label>
            <Textarea
              id="purpose"
              value={purpose}
              onChange={(event) => setPurpose(event.target.value)}
              placeholder="Required before submit-for-review — describe the business outcome."
              rows={3}
            />
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium" htmlFor="businessOutcome">
              Business outcome
            </label>
            <Textarea
              id="businessOutcome"
              value={businessOutcome}
              onChange={(event) => setBusinessOutcome(event.target.value)}
              placeholder="Measurable result this asset delivers for your org."
              rows={2}
            />
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <label className="text-sm font-medium" htmlFor="useCase">
                Use case
              </label>
              <Input
                id="useCase"
                value={useCase}
                onChange={(event) => setUseCase(event.target.value)}
                placeholder="Weekly pipeline review"
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium" htmlFor="estimatedHours">
                Est. hours saved / month
              </label>
              <Input
                id="estimatedHours"
                type="number"
                min={0}
                step={0.5}
                value={estimatedHours}
                onChange={(event) => setEstimatedHours(event.target.value)}
                placeholder="4"
              />
            </div>
          </div>
          <Button type="submit" disabled={busy}>
            {busy ? <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden /> : null}
            Save draft
          </Button>
        </form>
      </div>
    </AppShell>
  )
}
