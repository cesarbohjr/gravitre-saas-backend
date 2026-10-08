"use client"

import { useRef, useState } from "react"
import Link from "next/link"
import { useRouter } from "next/navigation"
import { AppShell } from "@/components/gravitre/app-shell"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { marketplaceApi } from "@/lib/api"
import { useAuth } from "@/lib/auth-context"
import { useOrgAdmin } from "@/lib/use-org-admin"
import { ArrowLeft, Loader2, PlusCircle } from "lucide-react"
import { toast } from "sonner"
import { ESTIMATED_HOURS_SAVED_MONTHLY } from "@/lib/outcome-labels"

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
  const { isAdmin, loading: roleLoading } = useOrgAdmin()
  const lock = useRef(false)
  const [saveError, setSaveError] = useState<string | null>(null)
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
  const [pricingType, setPricingType] = useState<
    "free" | "paid" | "subscription"
  >("free")
  const [priceDollars, setPriceDollars] = useState("0")

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
    if (lock.current || !isAdmin || !user) return
    const parsedHours = estimatedHours.trim()
      ? Number(estimatedHours)
      : undefined
    const amount = priceDollars.trim()
    const priceCents =
      pricingType === "free" ? 0 : Math.round(Number(amount) * 100)
    if (
      parsedHours != null &&
      (!Number.isFinite(parsedHours) || parsedHours < 0)
    ) {
      setSaveError("Estimated hours must be a finite number of zero or more.")
      return
    }
    if (
      pricingType !== "free" &&
      (!/^\d+(\.\d{1,2})?$/.test(amount) ||
        !Number.isSafeInteger(priceCents) ||
        priceCents < 1)
    ) {
      setSaveError(
        "Enter a positive USD amount with at most two decimal places.",
      )
      return
    }
    lock.current = true
    setSaveError(null)
    setBusy(true)
    try {
      const result = await marketplaceApi.createOrgAsset({
        slug: normalizedSlug,
        title: title.trim(),
        description: description.trim() || undefined,
        assetType: "ai_agent",
        department: department.trim() || undefined,
        businessOutcome: businessOutcome.trim() || undefined,
        useCase: useCase.trim() || undefined,
        estimatedHoursSaved:
          parsedHours != null && !Number.isNaN(parsedHours)
            ? parsedHours
            : undefined,
        config: {
          name: title.trim(),
          purpose: purpose.trim(),
          role: roleName.trim(),
          department: department.trim(),
          systems: [],
        },
        pricingType,
        priceCents,
      })
      toast.success("Draft asset created")
      router.push(
        `/marketplace/org-admin?created=${encodeURIComponent(result.asset.slug)}`,
      )
    } catch (err) {
      setSaveError(
        err instanceof Error
          ? err.message
          : "Could not create asset. Your draft is retained.",
      )
    } finally {
      lock.current = false
      setBusy(false)
    }
  }

  if (roleLoading)
    return (
      <AppShell title="Create org asset">
        <p role="status" className="p-6">
          Checking organization permissions…
        </p>
      </AppShell>
    )
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
      <div
        className="mx-auto max-w-xl space-y-6 px-4 pb-24 [&_[data-slot=button]]:min-h-11 [&_input]:min-h-11"
        data-composition="create"
      >
        <Button variant="ghost" size="sm" asChild className="-ml-2">
          <Link href="/marketplace/org-admin">
            <ArrowLeft className="mr-1.5 h-4 w-4" aria-hidden />
            Org admin
          </Link>
        </Button>

        <header>
          <h1 className="flex items-center gap-2 font-sans text-2xl font-medium">
            <PlusCircle className="h-5 w-5 text-primary" aria-hidden />
            Create an agent asset
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Save a draft AI agent for your organization. Submit it for review
            when ready to publish internally.
          </p>
        </header>

        <form
          onSubmit={handleSubmit}
          className="space-y-4 border-y border-[color:var(--g-border-subtle)] py-5"
        >
          <fieldset disabled={busy} className="min-w-0 space-y-4">
            <p className="text-xs font-medium text-muted-foreground">
              01 / Identity and purpose
            </p>
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
            <details className="border-t border-border py-2">
              <summary className="min-h-11 cursor-pointer py-3 text-sm font-medium">
                02 / Outcome estimates (optional)
              </summary>
              <div className="space-y-4">
                <div className="space-y-2">
                  <label
                    className="text-sm font-medium"
                    htmlFor="businessOutcome"
                  >
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
                    <label
                      className="text-sm font-medium"
                      htmlFor="estimatedHours"
                    >
                      {ESTIMATED_HOURS_SAVED_MONTHLY}
                    </label>
                    <Input
                      id="estimatedHours"
                      type="number"
                      min={0}
                      step={0.5}
                      value={estimatedHours}
                      onChange={(event) =>
                        setEstimatedHours(event.target.value)
                      }
                      placeholder="4"
                    />
                  </div>
                </div>
              </div>
            </details>
            <div className="space-y-3 border-t border-border py-3">
              <p className="text-xs font-medium text-muted-foreground">
                Pricing
              </p>
              <div className="flex flex-wrap gap-2">
                {(["free", "paid", "subscription"] as const).map((option) => (
                  <Button
                    key={option}
                    type="button"
                    size="sm"
                    variant={pricingType === option ? "default" : "outline"}
                    disabled={busy}
                    aria-pressed={pricingType === option}
                    onClick={() => setPricingType(option)}
                  >
                    {option === "free"
                      ? "Free"
                      : option === "paid"
                        ? "One-time"
                        : "Subscription"}
                  </Button>
                ))}
              </div>
              {pricingType !== "free" ? (
                <div className="flex max-w-xs items-center gap-2">
                  <span className="text-sm text-muted-foreground">$</span>
                  <Input
                    type="number"
                    min="0.01"
                    aria-label="Price in USD"
                    step="0.01"
                    value={priceDollars}
                    disabled={busy}
                    onChange={(event) => setPriceDollars(event.target.value)}
                  />
                  <span className="whitespace-nowrap text-xs text-muted-foreground">
                    {pricingType === "subscription" ? "/ month" : "once"}
                  </span>
                </div>
              ) : null}
            </div>
          </fieldset>
          {saveError ? (
            <p role="alert" className="text-sm text-destructive">
              {saveError}
            </p>
          ) : null}
          <Button type="submit" disabled={busy}>
            {busy ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden />
            ) : null}
            Save draft
          </Button>
        </form>
      </div>
    </AppShell>
  )
}
