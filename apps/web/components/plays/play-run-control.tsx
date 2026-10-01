"use client"

import { useState } from "react"
import { toast } from "sonner"
import { Button } from "@/components/ui/button"
import { apiFetch } from "@/lib/fetcher"
import { Play, ShieldCheck } from "lucide-react"

type Installation = { id: string; operatingMode: string; status: string }
type Readiness = { act_with_approval_ready?: boolean; act_within_policy_ready?: boolean }

export function PlayRunControl({ playKey, installation, readiness }: { playKey: string; installation: Installation | null; readiness: Readiness }) {
  const [running, setRunning] = useState(false)
  const [lastRun, setLastRun] = useState<{ id: string; status: string } | null>(null)
  const canActWithApproval = installation?.operatingMode === "ACT WITH APPROVAL" && Boolean(readiness.act_with_approval_ready)
  const canRun = Boolean(installation?.id && installation.status === "ready" && canActWithApproval)

  async function runPlay() {
    if (!installation || !canRun) return
    try {
      setRunning(true)
      const response = await apiFetch(`/api/plays/${playKey}/runs`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ installationId: installation.id }),
      })
      const payload = await response.json().catch(() => ({}))
      if (!response.ok) throw new Error(typeof payload.detail === "string" ? payload.detail : "Could not start Play")
      setLastRun({ id: String(payload.playRunId), status: String(payload.status) })
      toast.success(payload.status === "awaiting_approval" ? "Play started and is awaiting approval" : "Play started")
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Could not start Play")
    } finally {
      setRunning(false)
    }
  }

  if (!installation) return <p className="text-xs text-muted-foreground">Save Play setup before running it.</p>
  if (installation.operatingMode === "OBSERVE" || installation.operatingMode === "RECOMMEND") {
    return <p className="text-xs text-muted-foreground">This operating mode does not take external action. Action execution is available only after you explicitly choose an action mode.</p>
  }
  if (installation.operatingMode === "ACT WITHIN POLICY") {
    return <p className="text-xs text-muted-foreground">Act within policy stays locked until effective runtime action authorization can be proven for this Play.</p>
  }

  return (
    <div className="rounded-xl border border-divide p-4">
      <div className="flex items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 text-sm font-medium"><ShieldCheck className="size-4" />Run with approval</div>
          <p className="mt-1 max-w-xl text-xs leading-5 text-muted-foreground">Starts the workflows linked to this Play. Consequential actions remain in Gravitre's existing approval queue and cannot execute until approved.</p>
        </div>
        <Button onClick={runPlay} disabled={!canRun || running}><Play className="size-4" />{running ? "Starting…" : "Run play"}</Button>
      </div>
      {lastRun ? <p className="mt-3 border-t border-divide pt-3 text-xs text-muted-foreground">Play run {lastRun.id.slice(0, 8)} · {lastRun.status.replaceAll("_", " ")}</p> : null}
    </div>
  )
}
