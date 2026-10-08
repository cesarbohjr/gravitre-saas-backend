"use client"

import { useRef, useState } from "react"
import Link from "next/link"
import useSWR from "swr"
import { WorkSectionErrorCard } from "@/components/gravitre/work-section-error-card"
import { AppShell } from "@/components/gravitre/app-shell"
import { GravitrePageHeader } from "@/components/gravitre/nodus-product"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import { Textarea } from "@/components/ui/textarea"
import { marketplaceApi } from "@/lib/api"
import { fetcher } from "@/lib/fetcher"
import { useAuth } from "@/lib/auth-context"
import { Loader2, Package, ShieldCheck, ArrowLeft } from "lucide-react"
import { toast } from "sonner"
import type { PartnerConnectorSubmission } from "@/types/api"
import { Illustration } from "@/components/gravitre/illustration"

const CHECKLIST_ITEMS = [
  {
    key: "noHardcodedSecrets",
    label: "No hardcoded secrets in package or manifest",
  },
  {
    key: "oauthRedirectsDocumented",
    label: "OAuth redirect URLs documented and match Gravitre callback pattern",
  },
  {
    key: "scopesMinimized",
    label: "OAuth/API scopes are minimized to required actions only",
  },
  {
    key: "dataResidencyDocumented",
    label: "Data residency and retention documented for customer DPA",
  },
  {
    key: "auditLoggingCompatible",
    label: "Actions emit audit-compatible events (no PII in metadata)",
  },
  {
    key: "errorHandlingDocumented",
    label: "Error handling and rate-limit behavior documented",
  },
] as const

type ChecklistKey = (typeof CHECKLIST_ITEMS)[number]["key"]

const DEFAULT_MANIFEST = `{
  "manifestVersion": "1.0",
  "id": "com.example.myconnector",
  "name": "My Connector",
  "version": "1.0.0",
  "vendor": "my_connector",
  "description": "Short description for the marketplace catalog.",
  "auth": { "type": "apiKey", "headerName": "X-Api-Key" },
  "capabilities": ["actions"],
  "actions": [
    {
      "id": "items.list",
      "name": "List items",
      "scopes": ["my_connector:items:read", "my_connector:*"]
    }
  ]
}`

export default function MarketplaceSubmitPage() {
  const { user } = useAuth()
  const [manifestText, setManifestText] = useState(DEFAULT_MANIFEST)
  const [handlersSource, setHandlersSource] = useState(
    "# Optional: paste handlers.py for automated static analysis\n\ndef items_list(ctx, params):\n    return {'items': []}\n",
  )
  const [checklist, setChecklist] = useState<Record<ChecklistKey, boolean>>({
    noHardcodedSecrets: false,
    oauthRedirectsDocumented: false,
    scopesMinimized: false,
    dataResidencyDocumented: false,
    auditLoggingCompatible: false,
    errorHandlingDocumented: false,
  })
  const lock = useRef(false)
  const [failure, setFailure] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  const {
    data: mine,
    error,
    isLoading,
    mutate,
  } = useSWR<{ submissions: PartnerConnectorSubmission[] }>(
    user ? "/api/marketplace/submissions/mine" : null,
    fetcher,
  )

  const handleSubmit = async () => {
    if (lock.current || !user) return
    if (!CHECKLIST_ITEMS.every((item) => checklist[item.key])) return
    let manifest: Record<string, unknown>
    try {
      manifest = JSON.parse(manifestText) as Record<string, unknown>
      if (!manifest || Array.isArray(manifest) || typeof manifest !== "object")
        throw new Error("Manifest must be a JSON object")
    } catch {
      toast.error("Invalid JSON", {
        description: "Fix manifest.json syntax before submitting.",
      })
      return
    }

    lock.current = true
    setFailure(null)
    setIsSubmitting(true)
    try {
      const packageSources =
        handlersSource.trim() &&
        !handlersSource.trim().startsWith("# Optional:")
          ? { "handlers.py": handlersSource }
          : undefined
      await marketplaceApi.submit({
        manifest,
        securityChecklist: checklist,
        packageSources,
      })
      toast.success("Submission received", {
        description: "Your connector package is in the review queue.",
      })
      await Promise.allSettled([mutate()])
    } catch (err) {
      setFailure(
        err instanceof Error
          ? err.message
          : "The request failed. Your inputs are retained for retry.",
      )
    } finally {
      lock.current = false
      setIsSubmitting(false)
    }
  }

  const allChecked = CHECKLIST_ITEMS.every((item) => checklist[item.key])

  return (
    <AppShell title="Submit connector">
      <div
        data-composition="create"
        className="bg-[color:var(--g-canvas)] pb-24 [&_[data-slot=button]]:min-h-11 [&_input]:min-h-11"
      >
        <GravitrePageHeader
          art="dept-engineering"
          eyebrow="Partner marketplace"
          title="Submit connector package"
          description="Upload your manifest.json and complete the security checklist. Admins review submissions before connectors appear in the catalog."
          icon={<Package className="h-5 w-5" />}
          actions={
            <div className="flex gap-2">
              <Button variant="outline" size="sm" asChild>
                <Link href="/marketplace/billing">Billing</Link>
              </Button>
              <Button variant="outline" size="sm" asChild>
                <Link href="/marketplace/sandbox">Sandbox</Link>
              </Button>
              <Button variant="outline" size="sm" asChild>
                <Link href="/connectors">
                  <ArrowLeft className="h-3.5 w-3.5 mr-1.5" />
                  Connectors
                </Link>
              </Button>
            </div>
          }
        />

        <div className="mx-auto max-w-3xl space-y-8 px-[var(--np-page-pad-sm)] py-4 sm:px-[var(--np-page-pad)] sm:py-5">
          <fieldset disabled={isSubmitting} className="min-w-0 space-y-8">
            <section className="border-t border-border py-5 space-y-3">
              <h2 className="text-sm font-medium flex items-center gap-2">
                <ShieldCheck className="h-4 w-4 text-primary" />
                Security checklist
              </h2>
              <div className="space-y-3">
                {CHECKLIST_ITEMS.map((item) => (
                  <label
                    key={item.key}
                    className="flex min-h-11 items-start gap-3 py-2 text-sm cursor-pointer"
                  >
                    <Checkbox
                      checked={checklist[item.key]}
                      onCheckedChange={(checked) =>
                        setChecklist((prev) => ({
                          ...prev,
                          [item.key]: checked === true,
                        }))
                      }
                      className="mt-0.5"
                    />
                    <span className="text-muted-foreground">{item.label}</span>
                  </label>
                ))}
              </div>
            </section>

            <section className="rounded-lg border border-border bg-card p-5 space-y-3">
              <h2 className="text-sm font-medium">handlers.py (optional)</h2>
              <Textarea
                value={handlersSource}
                onChange={(e) => setHandlersSource(e.target.value)}
                className="font-mono text-xs min-h-[160px] bg-secondary/40"
                spellCheck={false}
              />
              <p className="text-xs text-muted-foreground">
                Include source for automated static analysis. Packages that pass
                scan + scope review earn the <strong>Gravitre Certified</strong>{" "}
                badge when published.
              </p>
            </section>

            <section className="rounded-lg border border-border bg-card p-5 space-y-3">
              <h2 className="text-sm font-medium">manifest.json</h2>
              <Textarea
                value={manifestText}
                onChange={(e) => setManifestText(e.target.value)}
                className="font-mono text-xs min-h-[320px] bg-secondary/40"
                spellCheck={false}
              />
              <p className="text-xs text-muted-foreground">
                Follow{" "}
                <code className="bg-secondary px-1 rounded">
                  docs/integration/connector-sdk-spec.md
                </code>{" "}
                in the repository for the full manifest schema.
              </p>
            </section>
          </fieldset>
          {failure ? (
            <p role="alert" className="text-sm text-destructive">
              {failure}
            </p>
          ) : null}
          <div className="flex flex-wrap items-center justify-between gap-3">
            <p className="text-xs text-muted-foreground">
              {allChecked
                ? "Checklist complete — ready to submit"
                : "Complete all checklist items to submit"}
            </p>
            <Button
              onClick={() => void handleSubmit()}
              disabled={!allChecked || isSubmitting}
            >
              {isSubmitting ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  Submitting...
                </>
              ) : (
                "Submit for review"
              )}
            </Button>
          </div>

          {error ? (
            <WorkSectionErrorCard
              title="Could not refresh your submissions"
              onRetry={() => void mutate()}
            />
          ) : null}
          {isLoading && !mine ? (
            <p role="status">Loading submissions…</p>
          ) : mine?.submissions.length === 0 ? (
            <div className="py-4 text-center">
              <Illustration name="moment-welcome" width={160} className="mx-auto mb-3" />
              <p className="text-sm text-muted-foreground">
                No submissions returned.
              </p>
            </div>
          ) : null}
          {(mine?.submissions?.length ?? 0) > 0 && (
            <section className="rounded-lg border border-border bg-card overflow-hidden">
              <div className="px-5 py-3 border-b border-border">
                <h2 className="text-sm font-medium">Your submissions</h2>
              </div>
              <ul className="divide-y divide-border">
                {mine!.submissions.map((sub) => (
                  <li
                    key={sub.id}
                    className="px-5 py-3 flex items-center justify-between text-sm"
                  >
                    <div>
                      <p className="font-medium">{sub.name}</p>
                      <p className="text-xs text-muted-foreground">
                        {sub.vendor} · v{sub.version}
                      </p>
                    </div>
                    <div className="flex flex-col items-end gap-1">
                      <span className="text-xs capitalize px-2 py-0.5 rounded-full bg-secondary text-muted-foreground">
                        {sub.status.replace("_", " ")}
                      </span>
                      {sub.certificationStatus && (
                        <span className="text-xs text-muted-foreground">
                          Certification: {sub.certificationStatus}
                        </span>
                      )}
                    </div>
                  </li>
                ))}
              </ul>
            </section>
          )}
        </div>
      </div>
    </AppShell>
  )
}
