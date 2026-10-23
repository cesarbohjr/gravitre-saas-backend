"use client"
import { useRef, useState } from "react"
import useSWR from "swr"
import { Button } from "@/components/ui/button"
import { apiFetch, fetcher, formatUnknownError } from "@/lib/fetcher"
import { getQuickOrgId } from "@/lib/org-context"

type Blueprint = { id: string; title: string; playCount: number; agentCount: number; skillPackages: string[] }
export function OutcomePackBlueprints({ onCreated }: { onCreated: () => Promise<unknown> }) {
  const orgId = getQuickOrgId()
  return <Blueprints key={orgId} orgId={orgId} onCreated={onCreated} />
}
function Blueprints({ orgId, onCreated }: { orgId: string | null; onCreated: () => Promise<unknown> }) {
  const endpoint = "/api/marketplace/outcome-pack-blueprints"
  const { data, error, mutate } = useSWR<{ blueprints: Blueprint[] }>([endpoint, orgId], () => fetcher(endpoint))
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState("")
  const lock = useRef(false)
  async function create(id: string) {
    if (lock.current) return
    lock.current = true
    setBusy(true)
    setMessage("")
    try {
      const response = await apiFetch(`${endpoint}/${encodeURIComponent(id)}/draft`, { method: "POST" })
      if (!response.ok) throw new Error("Could not prepare this draft. Retry or check workspace access.")
      await onCreated()
      setMessage("Workspace draft ready. Review skill packages, connect apps, and prepare the OBSERVE installation before collecting evidence.")
    } catch (cause) { setMessage(formatUnknownError(cause)) }
    finally { lock.current = false; setBusy(false) }
  }
  return <section aria-label="Outcome Pack blueprints" className="space-y-3 rounded-md border p-4">
    <h2 className="font-semibold">Start from an Outcome Pack blueprint</h2>
    <p className="text-sm text-muted-foreground">Creates a private workspace draft. Blueprints carry no production certification or measured savings.</p>
    {error ? <Button variant="outline" onClick={() => void mutate()}>Retry blueprints</Button> : !data ? <p role="status">Loading blueprints…</p> :
      <ul className="grid gap-3 sm:grid-cols-2">{data.blueprints.map(pack => <li key={pack.id} className="space-y-2 rounded-md border p-3">
        <h3 className="text-sm font-semibold">{pack.title}</h3>
        <p className="text-xs">{pack.playCount} Plays · {pack.agentCount} agents · {pack.skillPackages.length} skill packages</p>
        <Button size="sm" variant="outline" disabled={busy} onClick={() => void create(pack.id)}>Prepare workspace draft</Button>
      </li>)}</ul>}
    {message ? <p role="status" className="text-sm">{message}</p> : null}
  </section>
}
