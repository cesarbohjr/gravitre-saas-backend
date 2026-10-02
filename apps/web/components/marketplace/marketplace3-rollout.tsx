"use client"

import { useState } from "react"
import useSWR from "swr"
import Link from "next/link"
import { AlertCircle, ArrowRight, Loader2, RefreshCw, ShieldCheck } from "lucide-react"
import { toast } from "sonner"
import { organizationsApi } from "@/lib/api"
import { certificateLabel, marketplace3Api, parseEvidenceIds, type DepartmentReadiness } from "@/lib/marketplace3"
import { DepartmentWorkspace } from "@/components/marketplace/department-workspace"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { GravitreMetric } from "@/components/gravitre/nodus-product"

const gates: Record<string, string> = { seed_catalog: "Deploy catalog", live_production_runtime_evidence: "Collect live execution evidence", measured_outcome_evidence: "Measure business outcomes", promote_certified_pack: "Ready for publication", complete: "Outcome evidence verified", fix_fixture_or_contract_failures: "Repair pack contracts", governance_and_verification: "Complete governance", schema_runtime_readiness: "Complete runtime readiness" }

function PackControls({ pack, onUpdated }: { pack: DepartmentReadiness; onUpdated: () => Promise<unknown> }) {
  const [orgId, setOrgId] = useState("")
  const [runs, setRuns] = useState<Record<string, string>>({})
  const [events, setEvents] = useState("")
  const [busy, setBusy] = useState<string | null>(null)
  const [error, setError] = useState("")
  const [notice, setNotice] = useState("")
  const [preview, setPreview] = useState(false)
  const { data: orgs, error: orgError, isLoading: orgLoading } = useSWR("marketplace3-pilot-organizations", organizationsApi.list)
  const { data: blueprint, error: blueprintError, isLoading: blueprintLoading } = useSWR(preview ? ["marketplace3-blueprint", pack.slug] : null, () => marketplace3Api.blueprint(pack.slug))
  const act = async (action: "install-pilot" | "certify" | "promote") => {
    setError(""); setNotice(""); setBusy(action)
    try {
      let body: unknown = {}
      if (action !== "promote") {
        if (!orgId) throw new Error("Choose the tenant workspace first.")
        if (action === "install-pilot") body = { orgId, installVariables: {} }
        else {
          const runtimeEvidence: Record<string, { orgId: string; runIds: string[] }> = {}
          for (const provider of pack.requiredSystems ?? []) {
            const ids = parseEvidenceIds(runs[provider] ?? "")
            if (!ids.length) throw new Error(`Add stored production run IDs for ${provider}.`)
            runtimeEvidence[provider] = { orgId, runIds: ids }
          }
          const eventIds = parseEvidenceIds(events)
          body = { runtimeEvidence, outcomeEvidence: eventIds.length ? { orgId, eventIds } : {} }
        }
      }
      await marketplace3Api.action(pack.slug, action, body)
      const message = action === "install-pilot" ? "Observe pilot installed. Open this tenant with the workspace picker to review its Plays and capabilities." : action === "promote" ? "Pack published after fresh evidence verification." : "Evidence checked. Readiness reflects the resolved records."
      setNotice(message); toast.success(message); await onUpdated()
    } catch (e) { setError(e instanceof Error ? e.message : "Action failed") }
    finally { setBusy(null) }
  }
  return <div className="space-y-4 border-t pt-4">
    <div className="flex flex-wrap items-center gap-3"><Button variant="outline" size="sm" onClick={() => setPreview(true)} disabled={!pack.deployed}>Preview department</Button><Link className="text-xs font-medium text-primary hover:underline" href={`/marketplace/departments/${encodeURIComponent(pack.slug)}`}>Open installed workspace →</Link></div>
    <div className="space-y-2"><Label htmlFor={`tenant-${pack.slug}`}>Pilot tenant</Label><select id={`tenant-${pack.slug}`} value={orgId} onChange={e => setOrgId(e.target.value)} disabled={!!busy || orgLoading || !!orgError} className="block w-full rounded-lg border bg-background p-2 text-sm"><option value="">{orgLoading ? "Loading workspaces…" : "Choose an authorized workspace"}</option>{orgs?.organizations?.map(org => <option key={org.id} value={org.id}>{org.name}</option>)}</select>{orgError ? <p role="alert" className="text-xs text-destructive">Authorized workspaces could not be loaded. Refresh to retry.</p> : null}<p className="text-xs text-muted-foreground">Installation starts in Observe mode. Existing plan, connector, and capability review checks apply.</p></div>
    <Button size="sm" variant="outline" disabled={!!busy || !orgId || !pack.deployed || !pack.fixturePassed || pack.status !== "draft" || pack.certificationLevel !== "governed"} onClick={() => void act("install-pilot")}>{busy === "install-pilot" ? <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden /> : null}Install Observe pilot</Button>
    <details className="rounded-lg border p-3"><summary className="cursor-pointer text-sm font-medium">Submit live evidence</summary><div className="mt-4 space-y-4"><p className="text-xs text-muted-foreground">Use stored completed production executions. Dry runs, simulations, and user-provided success claims cannot certify this pack.</p>{(pack.requiredSystems ?? []).map(provider => <div key={provider} className="space-y-2"><Label htmlFor={`runs-${pack.slug}-${provider}`}>{provider} production run IDs</Label><Textarea id={`runs-${pack.slug}-${provider}`} value={runs[provider] ?? ""} onChange={e => setRuns({ ...runs, [provider]: e.target.value })} placeholder="Stored run UUIDs, one per line" rows={2} disabled={!!busy} /></div>)}<div className="space-y-2"><Label htmlFor={`events-${pack.slug}`}>Measured business result IDs (optional)</Label><Textarea id={`events-${pack.slug}`} value={events} onChange={e => setEvents(e.target.value)} placeholder="Stored outcome event UUIDs, one per line" rows={2} disabled={!!busy} /><p className="text-xs text-muted-foreground">Outcome verification requires recorded baselines, results, source records, and matching Play/KPI contracts.</p></div><Button size="sm" disabled={!!busy || !orgId || !pack.deployed} onClick={() => void act("certify")}>{busy === "certify" ? <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden /> : null}Verify stored evidence</Button></div></details>
    <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg bg-muted/30 p-3"><p className="max-w-md text-xs text-muted-foreground">Public release requires current production evidence and passing contracts. Publication rechecks proof on the server.</p><Button size="sm" disabled={!!busy || !pack.publishReady || pack.status === "published"} onClick={() => void act("promote")}>{busy === "promote" ? <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden /> : null}Publish verified pack</Button></div>
    {error ? <p role="alert" className="rounded-lg border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive">{error}</p> : null}{notice ? <p role="status" className="rounded-lg border p-3 text-sm">{notice}</p> : null}
    <Dialog open={preview} onOpenChange={setPreview}><DialogContent className="max-h-[90dvh] overflow-y-auto sm:max-w-6xl"><DialogHeader><DialogTitle>Department preview</DialogTitle><DialogDescription>Pack blueprint; no live tenant results are included.</DialogDescription></DialogHeader>{blueprintLoading ? <p role="status">Loading department…</p> : blueprintError ? <p role="alert">Could not load this blueprint.</p> : blueprint ? <DepartmentWorkspace workspace={blueprint} preview /> : null}</DialogContent></Dialog>
  </div>
}

export function Marketplace3Rollout() {
  const { data, error, isLoading, mutate } = useSWR("marketplace3-live-readiness", marketplace3Api.readiness, { revalidateOnFocus: false })
  const [selected, setSelected] = useState<string | null>(null)
  const pack = data?.packs.find(p => p.slug === selected)
  return <section className="space-y-5" aria-label="Department pack rollout">
    <header className="flex flex-wrap items-start justify-between gap-3"><div><h2 className="flex items-center gap-2 text-lg font-semibold"><ShieldCheck className="h-5 w-5" aria-hidden />Marketplace 3.0 rollout</h2><p className="mt-1 text-sm text-muted-foreground">Deploy department pilots, inspect live readiness, and publish with verified evidence.</p></div><Button variant="outline" size="sm" onClick={() => void mutate()} disabled={isLoading}><RefreshCw className="mr-2 h-4 w-4" aria-hidden />Refresh</Button></header>
    {isLoading && !data ? <p role="status">Loading deployed department readiness…</p> : error ? <div role="alert" className="rounded-xl border border-destructive/30 p-4 text-sm"><AlertCircle className="mb-2 h-4 w-4" aria-hidden />Readiness is unavailable. Retry to load the current catalog.</div> : data ? <>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4"><GravitreMetric label="Deployed packs" value={`${data.deployedPackCount}/${data.packCount}`} /><GravitreMetric label="Governed" value={data.governedCount} /><GravitreMetric label="Production verified" value={data.productionVerifiedCount} /><GravitreMetric label="Outcome verified" value={data.outcomeVerifiedCount} /></div>
      <div className="grid gap-3 sm:grid-cols-2">{data.packs.map(p => <button type="button" key={p.slug} onClick={() => setSelected(p.slug)} aria-pressed={selected === p.slug} className={`rounded-xl border p-4 text-left transition-colors hover:bg-muted/30 ${selected === p.slug ? "border-primary bg-primary/5" : "bg-card"}`}><div className="flex flex-wrap items-center justify-between gap-2"><span className="text-sm font-semibold">{p.title}</span><Badge variant="outline">{p.deployed ? certificateLabel(p.certificationLevel) : "Not deployed"}</Badge></div><p className="mt-2 text-xs text-muted-foreground">{p.playCount ?? "—"} Plays · {p.agentCount ?? "—"} agents · {p.kpiCount ?? "—"} KPIs</p><p className="mt-2 text-xs font-medium">{gates[p.nextGate] ?? "Review readiness"}<ArrowRight className="ml-1 inline h-3 w-3" aria-hidden /></p></button>)}</div>
      {pack ? <article className="rounded-xl border bg-card p-5"><h3 className="text-base font-semibold">{pack.title}</h3><div className="my-3 flex flex-wrap gap-2"><Badge variant="outline">{pack.status}</Badge><Badge variant="outline">{pack.fixturePassed ? "Contracts pass" : "Contract repairs required"}</Badge>{(pack.requiredSystems ?? []).map(p => <Badge key={p} variant="secondary">{p}</Badge>)}</div><p className="text-xs text-muted-foreground">Live evidence: {(pack.runtimeEvidenceProviders ?? []).join(", ") || "none"} · Measured outcomes: {pack.measuredOutcomeCount ?? 0}</p>{pack.storedCertificationLevel && pack.storedCertificationLevel !== pack.certificationLevel ? <p className="mt-2 text-xs text-destructive">Stored certification differs from current resolved proof. Publication uses the fresh evidence gate.</p> : null}{pack.blockingFindingCodes.length ? <p role="alert" className="mt-2 text-xs text-destructive">{pack.blockingFindingCodes.join(", ")}</p> : null}<PackControls key={pack.slug} pack={pack} onUpdated={mutate} /></article> : <p className="text-sm text-muted-foreground">Select a department to inspect its blueprint and rollout controls.</p>}
    </> : null}
  </section>
}
