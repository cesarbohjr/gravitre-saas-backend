"use client"

import { useRef, useState } from "react"
import useSWR from "swr"
import { Button } from "@/components/ui/button"
import { apiFetch, fetcher, formatUnknownError } from "@/lib/fetcher"
import { getQuickOrgId } from "@/lib/org-context"

type Report = { findings?: Array<{ code: string; message: string }> }
type Certificate = { level: string; publishReady: boolean; report?: Report }
type Status = { publishReady: boolean; certification: Certificate | null }
type RunResult = { report?: Report }

export function OutcomePackCertification({ assetRef }: { assetRef: string }) {
  const orgId = getQuickOrgId()
  return <CertificationPanel key={`${orgId}:${assetRef}`} assetRef={assetRef} orgId={orgId} />
}

function CertificationPanel({ assetRef, orgId }: { assetRef: string; orgId: string | null }) {
  const endpoint = `/api/marketplace/assets/${encodeURIComponent(assetRef)}/certification`
  const { data, error, mutate } = useSWR<Status>([endpoint, orgId], () => fetcher<Status>(endpoint))
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState("")
  const [report, setReport] = useState<Report | undefined>()
  const lock = useRef(false)
  const certificate = data?.certification
  const ready = !error && data?.publishReady === true && certificate?.publishReady === true &&
    ["production_verified", "outcome_verified"].includes(certificate.level)

  async function run(mode: "fixture" | "production") {
    if (lock.current) return
    lock.current = true
    setBusy(true)
    setMessage("")
    setReport(undefined)
    try {
      const response = await apiFetch(`${endpoint}/run`, {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ mode }),
      })
      if (!response.ok) throw new Error("Certification check failed. Retry or review your workspace access.")
      const result: RunResult = await response.json()
      setReport(result.report)
      setMessage(mode === "fixture" ? "Configuration checked. Production evidence is still required." : "Production evidence collected. Review the current publication status.")
      await mutate()
    } catch (cause) {
      setMessage(formatUnknownError(cause))
    } finally {
      lock.current = false
      setBusy(false)
    }
  }

  return <section aria-label="Outcome Pack certification" className="space-y-3 rounded-md border p-3">
    <h4 className="text-sm font-semibold">Publication evidence</h4>
    <p role="status" className="text-sm">{error ? "Evidence unavailable. Retry before publication." : !data ? "Checking current evidence…" : ready ? "Production evidence verified for this configuration." : "Production evidence required before publication."}</p>
    <div className="flex flex-wrap gap-2">
      <Button variant="outline" size="sm" disabled={busy} onClick={() => void run("fixture")}>Check configuration</Button>
      <Button variant="outline" size="sm" disabled={busy} onClick={() => void run("production")}>Collect production evidence</Button>
      {error ? <Button variant="ghost" size="sm" disabled={busy} onClick={() => void mutate()}>Retry status</Button> : null}
    </div>
    <p className="text-xs text-muted-foreground">Checks inspect existing evidence. Publication still requires the normal approval review.</p>
    {message ? <p role="status" className="text-sm">{message}</p> : null}
    {(report ?? certificate?.report)?.findings?.length ? <ul className="list-disc pl-5 text-sm">{(report ?? certificate?.report)?.findings?.map((finding, index) => <li key={`${finding.code}-${index}`}>{finding.message}</li>)}</ul> : null}
  </section>
}
