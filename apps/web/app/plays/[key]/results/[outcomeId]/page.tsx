"use client"

import Link from "next/link"
import { useParams } from "next/navigation"
import useSWR from "swr"
import { AppShell } from "@/components/gravitre/app-shell"
import { GravitrePageHeader } from "@/components/gravitre/nodus-product"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { fetcher } from "@/lib/fetcher"
import { WorkSectionErrorCard } from "@/components/gravitre/work-section-error-card"
import { TYPE } from "@/lib/design-system"
import { ArrowLeft, CheckCircle2 } from "lucide-react"

type Evidence = {
  metric?: { key?: string; baseline?: number; result?: number; delta?: number; unit?: string; currency?: string; measuredAt?: string }
  play?: { key?: string; runId?: string; installationId?: string }
  workflow?: { id?: string; runId?: string }
  governance?: { approvalStatus?: string; requiredApprovals?: number; approvals?: Array<Record<string, unknown>> }
  sourceRecords?: Array<{ system?: string; record_type?: string; record_id?: string }>
  verification?: { state?: string; method?: string; verified?: boolean; confidence?: number }
  attribution?: { type?: string; weight?: number }
  truth?: { executionSuccessIsBusinessSuccess?: boolean; sourceOfRecordRequiredForVerifiedSuccess?: boolean }
}
type Payload = { playKey: string; evidence: Evidence }

export default function PlayResultEvidencePage() {
  const params = useParams<{ key: string; outcomeId: string }>()
  const { data, error } = useSWR<Payload>(`/api/plays/${params.key}/outcomes/${params.outcomeId}/evidence`, fetcher)
  const e = data?.evidence
  return <AppShell title="Result evidence"><div className="mx-auto max-w-4xl">
    <GravitrePageHeader eyebrow="Play result" title="Evidence" description="Trace this business result from measured change back through execution, governance, and its source of record." actions={<Button variant="ghost" size="sm" asChild><Link href={`/plays/${params.key}`}><ArrowLeft className="size-4" />Back to play</Link></Button>} />
    <div className="space-y-4 px-[var(--np-page-pad-sm)] pb-8 sm:px-[var(--np-page-pad)]">
      {error ? <WorkSectionErrorCard title="Could not load result evidence" message="The evidence endpoint did not return this outcome." /> : !e ? <p className="text-sm text-muted-foreground">Loading evidence…</p> : <>
        <section className="border-b border-divide py-5">
          <div className="flex items-center gap-2"><CheckCircle2 className={`size-5 ${e.verification?.verified ? "text-success" : "text-muted-foreground"}`} /><h2 className="font-semibold">{e.verification?.state ?? "Unverified"}</h2></div>
          <div className="mt-4 grid gap-3 sm:grid-cols-3">
            <div><p className={TYPE.eyebrow}>Metric</p><p className="text-sm font-medium">{e.metric?.key?.replaceAll("_", " ") ?? "—"}</p></div>
            <div><p className={TYPE.eyebrow}>Measured change</p><p className="text-sm font-medium">{typeof e.metric?.delta === "number" ? `${e.metric.currency ? `${e.metric.currency} ` : ""}${e.metric.delta.toLocaleString()}` : "—"}</p></div>
            <div><p className={TYPE.eyebrow}>Verification</p><p className="text-sm font-medium">{e.verification?.method ?? "Not verified"}</p></div>
          </div>
        </section>
        <section className="grid gap-4 border-b border-divide py-5 sm:grid-cols-2">
          <div><p className={TYPE.eyebrow}>Execution</p><p className="mt-2 text-sm">Play run <span className="font-mono">{e.play?.runId ?? "—"}</span></p><p className="mt-1 text-sm">Workflow run <span className="font-mono">{e.workflow?.runId ?? "—"}</span></p></div>
          <div><p className={TYPE.eyebrow}>Governance</p><p className="mt-2 text-sm">Approval status: {e.governance?.approvalStatus ?? "—"}</p><p className="mt-1 text-sm">Required approvals: {typeof e.governance?.requiredApprovals === "number" ? e.governance.requiredApprovals : "Not reported"}</p></div>
        </section>
        <section className="border-b border-divide py-5"><p className={TYPE.eyebrow}>Source of record</p>{e.sourceRecords?.length ? <div className="mt-3 space-y-2">{e.sourceRecords.map((r,i)=><div key={i} className="flex flex-wrap gap-2 text-sm"><Badge variant="outline">{r.system ?? "source"}</Badge><span>{r.record_type ?? "record"} · {r.record_id ?? "—"}</span></div>)}</div> : <p className="mt-2 text-sm text-muted-foreground">No source-of-record evidence attached.</p>}</section>
        <p className="text-xs text-muted-foreground">Execution success is never treated as business success. Verified success requires source-of-record evidence and a measured metric change.</p>
      </>}
    </div>
  </div></AppShell>
}
