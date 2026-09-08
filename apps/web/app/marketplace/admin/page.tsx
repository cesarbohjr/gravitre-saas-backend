"use client"

import { useState } from "react"
import Link from "next/link"
import useSWR from "swr"
import { AppShell } from "@/components/gravitre/app-shell"
import {
  GravitreEmpty,
  GravitreMetric,
  GravitrePageHeader,
  GravitreSurface,
} from "@/components/gravitre/nodus-product"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { StatusBadge } from "@/components/gravitre/status-badge"
import { marketplaceApi } from "@/lib/api"
import { fetcher } from "@/lib/fetcher"
import { useAuth } from "@/lib/auth-context"
import { useOrgAdmin } from "@/lib/use-org-admin"
import { CheckCircle2, Loader2, RefreshCw, ShieldCheck, XCircle, ArrowLeft } from "lucide-react"
import { NucleoApproval } from "@/components/icons/nucleo/semantic"
import { toast } from "sonner"
import type { MarketplaceRegistryConnector, PartnerConnectorSubmission } from "@/types/api"

const STATUS_VARIANT: Record<string, "success" | "error" | "warning" | "muted"> = {
  pending: "warning",
  in_review: "warning",
  approved: "success",
  rejected: "error",
  withdrawn: "muted",
}

const CERT_VARIANT: Record<string, "success" | "error" | "warning" | "muted"> = {
  passed: "success",
  failed: "error",
  pending: "warning",
}

function CertificationSummary({ submission }: { submission: PartnerConnectorSubmission }) {
  const scan = submission.securityScan
  const scope = submission.scopeReview
  if (!scan && !scope) return null

  return (
    <div className="mt-3 space-y-2 rounded-[var(--np-radius-md)] border border-divide bg-[color:var(--g-surface-2)] p-3 text-xs">
      <div className="flex flex-wrap items-center gap-2">
        {submission.certificationStatus && (
          <StatusBadge variant={CERT_VARIANT[submission.certificationStatus] ?? "muted"}>
            cert {submission.certificationStatus}
          </StatusBadge>
        )}
        {scan && (
          <span className="text-muted-foreground">
            {scan.filesScanned} file(s) scanned · {scan.criticalCount ?? 0} critical ·{" "}
            {scan.warningCount ?? 0} warning
          </span>
        )}
        {(submission.packageSourceFiles?.length ?? 0) > 0 && (
          <span className="text-muted-foreground">Sources: {submission.packageSourceFiles?.join(", ")}</span>
        )}
      </div>
      {(scan?.findings?.length ?? 0) > 0 && (
        <ul className="space-y-1 text-muted-foreground">
          {scan!.findings.slice(0, 4).map((finding, idx) => (
            <li key={`${finding.code}-${idx}`}>
              <span className={finding.severity === "critical" ? "text-destructive" : ""}>
                [{finding.severity}] {finding.message}
                {finding.file ? ` (${finding.file}${finding.line ? `:${finding.line}` : ""})` : ""}
              </span>
            </li>
          ))}
        </ul>
      )}
      {(scope?.entries?.length ?? 0) > 0 && (
        <ul className="space-y-1 text-muted-foreground">
          {(scope?.entries ?? [])
            .flatMap((entry) => entry.issues.map((issue) => ({ actionKey: entry.actionKey, issue })))
            .slice(0, 3)
            .map((item, idx) => (
              <li key={`${item.actionKey}-${idx}`}>
                {item.actionKey}: {item.issue}
              </li>
            ))}
        </ul>
      )}
    </div>
  )
}

export default function MarketplaceAdminPage() {
  const { user } = useAuth()
  const { isAdmin } = useOrgAdmin()
  const [reviewTarget, setReviewTarget] = useState<PartnerConnectorSubmission | null>(null)
  const [decision, setDecision] = useState<"approve" | "reject" | null>(null)
  const [notes, setNotes] = useState("")
  const [isReviewing, setIsReviewing] = useState(false)
  const [rescanningId, setRescanningId] = useState<string | null>(null)

  const { data, error, isLoading, mutate } = useSWR<{ submissions: PartnerConnectorSubmission[] }>(
    user && isAdmin ? "/api/marketplace/submissions" : null,
    fetcher
  )

  const { data: registry, mutate: mutateRegistry } = useSWR<{ connectors: MarketplaceRegistryConnector[] }>(
    user && isAdmin ? "/api/marketplace/registry" : null,
    fetcher
  )

  const rescanSubmission = async (submissionId: string) => {
    setRescanningId(submissionId)
    try {
      await marketplaceApi.rescan(submissionId)
      toast.success("Certification scan complete")
      await mutate()
    } catch (err) {
      toast.error("Rescan failed", {
        description: err instanceof Error ? err.message : "Please try again",
      })
    } finally {
      setRescanningId(null)
    }
  }

  const openReview = (submission: PartnerConnectorSubmission, next: "approve" | "reject") => {
    setReviewTarget(submission)
    setDecision(next)
    setNotes("")
  }

  const submitReview = async () => {
    if (!reviewTarget || !decision) return
    setIsReviewing(true)
    try {
      await marketplaceApi.review(reviewTarget.id, { decision, notes: notes.trim() || undefined })
      toast.success(decision === "approve" ? "Connector published" : "Submission rejected", {
        description: reviewTarget.name,
      })
      setReviewTarget(null)
      setDecision(null)
      await Promise.all([mutate(), mutateRegistry()])
    } catch (err) {
      toast.error("Review failed", {
        description: err instanceof Error ? err.message : "Please try again",
      })
    } finally {
      setIsReviewing(false)
    }
  }

  if (!isAdmin) {
    return (
      <AppShell title="Marketplace review">
        <div className="bg-[color:var(--g-canvas)]">
          <div className="mx-auto max-w-lg space-y-4 px-[var(--np-page-pad-sm)] py-6 sm:px-[var(--np-page-pad)]">
            <p className="text-sm text-muted-foreground">
              Admin access is required to review partner connector submissions.
            </p>
            <Button variant="outline" size="sm" asChild>
              <Link href="/connectors">Back to connectors</Link>
            </Button>
          </div>
        </div>
      </AppShell>
    )
  }

  const submissions = data?.submissions ?? []
  const pending = submissions.filter((s) => s.status === "pending" || s.status === "in_review")
  const published = registry?.connectors ?? []
  const history = submissions.filter((s) => s.status === "approved" || s.status === "rejected")

  return (
    <AppShell title="Marketplace review">
      <div className="bg-[color:var(--g-canvas)]">
        <GravitrePageHeader
          eyebrow="Partner marketplace · Admin"
          title="Connector review queue"
          description="Approve submissions to publish connectors to the org catalog. All reviewer actions are audit-logged."
          icon={<NucleoApproval className="h-5 w-5" />}
          actions={
            <div className="flex flex-wrap gap-2">
              <Button variant="outline" size="sm" asChild>
                <Link href="/marketplace/private">Private</Link>
              </Button>
              <Button variant="outline" size="sm" asChild>
                <Link href="/marketplace/billing">Billing</Link>
              </Button>
              <Button variant="outline" size="sm" asChild>
                <Link href="/marketplace/sandbox">Sandbox</Link>
              </Button>
              <Button variant="outline" size="sm" asChild>
                <Link href="/marketplace/submit">Submit package</Link>
              </Button>
              <Button variant="outline" size="sm" asChild>
                <Link href="/connectors">
                  <ArrowLeft className="mr-1.5 h-3.5 w-3.5" />
                  Connectors
                </Link>
              </Button>
            </div>
          }
        />

        <div className="mx-auto max-w-5xl space-y-6 px-[var(--np-page-pad-sm)] py-4 sm:px-[var(--np-page-pad)] sm:py-5">
          <section className="grid grid-cols-2 gap-[var(--np-kpi-gap)] sm:grid-cols-3">
            <GravitreMetric
              label="Pending review"
              value={isLoading ? "—" : pending.length}
              hint={isLoading ? "Loading" : "Awaiting decision"}
            />
            <GravitreMetric
              label="Published"
              value={registry ? published.length : "—"}
              hint="Registry entries"
            />
            <GravitreMetric
              label="Review history"
              value={isLoading ? "—" : history.length}
              hint="Approved or rejected"
            />
          </section>

          {isLoading && (
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" />
              Loading submissions...
            </div>
          )}
          {error && (
            <p className="text-sm text-destructive">Failed to load submissions. Check backend connectivity.</p>
          )}

          <GravitreSurface padded={false} className="overflow-hidden">
            <div className="flex items-center justify-between border-b border-divide px-4 py-3">
              <h2 className="text-sm font-medium">Pending review ({pending.length})</h2>
            </div>
            {pending.length === 0 ? (
              <GravitreEmpty
                className="border-0 shadow-none"
                title="No submissions awaiting review"
                hint="Partner packages appear here when submitted for certification."
              />
            ) : (
              <ul className="divide-y divide-[color:var(--g-border)]">
                {pending.map((sub) => (
                  <li key={sub.id} className="flex flex-col gap-4 px-4 py-4 sm:flex-row sm:items-center">
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <p className="font-medium">{sub.name}</p>
                        <StatusBadge variant={STATUS_VARIANT[sub.status] ?? "muted"}>
                          {sub.status.replace("_", " ")}
                        </StatusBadge>
                      </div>
                      <p className="mt-1 text-xs text-muted-foreground">
                        {sub.vendor} · v{sub.version} · {sub.packageId}
                      </p>
                      <p className="mt-1 text-xs text-muted-foreground">
                        Submitted {sub.createdAt ? new Date(sub.createdAt).toLocaleString() : "—"}
                      </p>
                      <CertificationSummary submission={sub} />
                    </div>
                    <div className="flex shrink-0 gap-2">
                      <Button
                        size="sm"
                        variant="outline"
                        className="gap-1.5"
                        disabled={rescanningId === sub.id}
                        onClick={() => void rescanSubmission(sub.id)}
                      >
                        {rescanningId === sub.id ? (
                          <Loader2 className="h-3.5 w-3.5 animate-spin" />
                        ) : (
                          <RefreshCw className="h-3.5 w-3.5" />
                        )}
                        Rescan
                      </Button>
                      <Button size="sm" variant="outline" className="gap-1.5" onClick={() => openReview(sub, "reject")}>
                        <XCircle className="h-3.5 w-3.5" />
                        Reject
                      </Button>
                      <Button size="sm" className="gap-1.5" onClick={() => openReview(sub, "approve")}>
                        <CheckCircle2 className="h-3.5 w-3.5" />
                        Approve
                      </Button>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </GravitreSurface>

          <GravitreSurface padded={false} className="overflow-hidden">
            <div className="border-b border-divide px-4 py-3">
              <h2 className="text-sm font-medium">Published registry ({published.length})</h2>
            </div>
            {published.length === 0 ? (
              <GravitreEmpty
                className="border-0 shadow-none"
                title="No published partner connectors yet"
                hint="Approved submissions appear in the org catalog registry."
              />
            ) : (
              <ul className="divide-y divide-[color:var(--g-border)]">
                {published.map((entry) => (
                  <li key={entry.vendor} className="flex items-center justify-between gap-3 px-4 py-3 text-sm">
                    <div className="flex min-w-0 items-center gap-2">
                      <span className="font-medium">{entry.name}</span>
                      {entry.certificationBadge === "gravitre_certified" && (
                        <span className="inline-flex shrink-0 items-center gap-1 rounded-[var(--np-radius-md)] bg-[color:var(--g-brand-soft)] px-2 py-0.5 text-xs text-[color:var(--g-brand)]">
                          <ShieldCheck className="h-3 w-3" />
                          Certified
                        </span>
                      )}
                    </div>
                    <span className="shrink-0 text-muted-foreground">
                      {entry.vendor} · v{entry.version}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </GravitreSurface>

          {history.length > 0 && (
            <GravitreSurface padded={false} className="overflow-hidden">
              <div className="border-b border-divide px-4 py-3">
                <h2 className="text-sm font-medium">Review history</h2>
              </div>
              <ul className="divide-y divide-[color:var(--g-border)]">
                {history.map((sub) => (
                  <li key={sub.id} className="px-4 py-3 text-sm">
                    <div className="flex items-center gap-2">
                      <span className="font-medium">{sub.name}</span>
                      <StatusBadge variant={STATUS_VARIANT[sub.status] ?? "muted"}>{sub.status}</StatusBadge>
                    </div>
                    {sub.reviewNotes && (
                      <p className="mt-1 text-xs text-muted-foreground">{sub.reviewNotes}</p>
                    )}
                  </li>
                ))}
              </ul>
            </GravitreSurface>
          )}
        </div>
      </div>

      <Dialog open={!!reviewTarget} onOpenChange={(open) => !open && setReviewTarget(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{decision === "approve" ? "Approve" : "Reject"} submission</DialogTitle>
            <DialogDescription>
              {reviewTarget?.name} ({reviewTarget?.vendor})
              {reviewTarget?.certificationStatus === "passed"
                ? " — eligible for Gravitre Certified badge"
                : reviewTarget?.certificationStatus === "failed"
                  ? " — certification failed; badge will not be applied"
                  : " — certification pending (no source or incomplete scan)"}
            </DialogDescription>
          </DialogHeader>
          {reviewTarget && <CertificationSummary submission={reviewTarget} />}
          <Textarea
            placeholder="Reviewer notes (optional for approve, recommended for reject)"
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            className="min-h-[100px]"
          />
          <DialogFooter>
            <Button variant="outline" onClick={() => setReviewTarget(null)}>
              Cancel
            </Button>
            <Button
              variant={decision === "reject" ? "destructive" : "default"}
              onClick={() => void submitReview()}
              disabled={isReviewing}
            >
              {isReviewing ? <Loader2 className="h-4 w-4 animate-spin" /> : decision === "approve" ? "Publish" : "Reject"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </AppShell>
  )
}
