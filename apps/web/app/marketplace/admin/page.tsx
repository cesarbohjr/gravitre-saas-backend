"use client"

import { useState } from "react"
import Link from "next/link"
import useSWR from "swr"
import { AppShell } from "@/components/gravitre/app-shell"
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
import { CheckCircle2, Loader2, RefreshCw, Shield, ShieldCheck, XCircle, ArrowLeft } from "lucide-react"
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
    <div className="mt-3 rounded-md border border-border bg-secondary/30 p-3 text-xs space-y-2">
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
          {scope.entries
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
  const isAdmin = user?.role === "admin" || user?.role === "owner"
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
        <div className="p-6 max-w-lg">
          <p className="text-sm text-muted-foreground">
            Admin access is required to review partner connector submissions.
          </p>
          <Button variant="outline" size="sm" className="mt-4" asChild>
            <Link href="/connectors">Back to connectors</Link>
          </Button>
        </div>
      </AppShell>
    )
  }

  const submissions = data?.submissions ?? []
  const pending = submissions.filter((s) => s.status === "pending" || s.status === "in_review")
  const published = registry?.connectors ?? []

  return (
    <AppShell title="Marketplace review">
      <div className="p-6 space-y-8 max-w-5xl">
        <div className="flex items-start justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 text-sm text-muted-foreground mb-2">
              <Shield className="h-4 w-4" />
              Partner marketplace · Admin
            </div>
            <h1 className="text-2xl font-semibold">Connector review queue</h1>
            <p className="text-sm text-muted-foreground mt-1">
              Approve submissions to publish connectors to the org catalog. All reviewer actions are audit-logged.
            </p>
          </div>
          <div className="flex gap-2">
            <Button variant="outline" size="sm" asChild>
              <Link href="/marketplace/billing">Billing</Link>
              <Link href="/marketplace/sandbox">Sandbox</Link>
            </Button>
            <Button variant="outline" size="sm" asChild>
              <Link href="/marketplace/submit">Submit package</Link>
            </Button>
            <Button variant="outline" size="sm" asChild>
              <Link href="/connectors">
                <ArrowLeft className="h-3.5 w-3.5 mr-1.5" />
                Connectors
              </Link>
            </Button>
          </div>
        </div>

        {isLoading && (
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" />
            Loading submissions...
          </div>
        )}
        {error && (
          <p className="text-sm text-destructive">Failed to load submissions. Check backend connectivity.</p>
        )}

        <section className="rounded-lg border border-border bg-card overflow-hidden">
          <div className="px-4 py-3 border-b border-border flex items-center justify-between">
            <h2 className="text-sm font-medium">Pending review ({pending.length})</h2>
          </div>
          {pending.length === 0 ? (
            <p className="px-4 py-8 text-sm text-muted-foreground text-center">No submissions awaiting review.</p>
          ) : (
            <ul className="divide-y divide-border">
              {pending.map((sub) => (
                <li key={sub.id} className="px-4 py-4 flex flex-col sm:flex-row sm:items-center gap-4">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <p className="font-medium">{sub.name}</p>
                      <StatusBadge variant={STATUS_VARIANT[sub.status] ?? "muted"}>
                        {sub.status.replace("_", " ")}
                      </StatusBadge>
                    </div>
                    <p className="text-xs text-muted-foreground mt-1">
                      {sub.vendor} · v{sub.version} · {sub.packageId}
                    </p>
                    <p className="text-xs text-muted-foreground mt-1">
                      Submitted {sub.createdAt ? new Date(sub.createdAt).toLocaleString() : "—"}
                    </p>
                    <CertificationSummary submission={sub} />
                  </div>
                  <div className="flex gap-2 shrink-0">
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
        </section>

        <section className="rounded-lg border border-border bg-card overflow-hidden">
          <div className="px-4 py-3 border-b border-border">
            <h2 className="text-sm font-medium">Published registry ({published.length})</h2>
          </div>
          {published.length === 0 ? (
            <p className="px-4 py-6 text-sm text-muted-foreground">No published partner connectors yet.</p>
          ) : (
            <ul className="divide-y divide-border">
              {published.map((entry) => (
                <li key={entry.vendor} className="px-4 py-3 text-sm flex justify-between items-center gap-3">
                  <div className="flex items-center gap-2 min-w-0">
                    <span className="font-medium">{entry.name}</span>
                    {entry.certificationBadge === "gravitre_certified" && (
                      <span className="inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full bg-primary/10 text-primary shrink-0">
                        <ShieldCheck className="h-3 w-3" />
                        Certified
                      </span>
                    )}
                  </div>
                  <span className="text-muted-foreground shrink-0">
                    {entry.vendor} · v{entry.version}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </section>

        {submissions.filter((s) => s.status === "approved" || s.status === "rejected").length > 0 && (
          <section className="rounded-lg border border-border bg-card overflow-hidden">
            <div className="px-4 py-3 border-b border-border">
              <h2 className="text-sm font-medium">Review history</h2>
            </div>
            <ul className="divide-y divide-border">
              {submissions
                .filter((s) => s.status === "approved" || s.status === "rejected")
                .map((sub) => (
                  <li key={sub.id} className="px-4 py-3 text-sm">
                    <div className="flex items-center gap-2">
                      <span className="font-medium">{sub.name}</span>
                      <StatusBadge variant={STATUS_VARIANT[sub.status] ?? "muted"}>{sub.status}</StatusBadge>
                    </div>
                    {sub.reviewNotes && (
                      <p className="text-xs text-muted-foreground mt-1">{sub.reviewNotes}</p>
                    )}
                  </li>
                ))}
            </ul>
          </section>
        )}
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
