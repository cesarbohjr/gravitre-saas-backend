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
  const disabledReason = !installation?.id
    ? "Save Play setup before running it."
    : installation.status !== "ready"
      ? "Play setup is not marked ready."
      : !readiness.act_with_approval_ready
        ? "This Play is not ready to act with approval."
        : installation.operatingMode !== "ACT WITH APPROVAL"
          ? "Choose Act with approval and save setup before running."
          : ""

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

  const note = (text: string) => (
    <div className="flex items-start gap-3 rounded-[12px] border border-divide bg-[color:var(--g-surface-1)] p-4">
      <ShieldCheck className="mt-0.5 size-4 shrink-0 text-muted-foreground" aria-hidden />
      <p className="text-[13px] leading-5 text-muted-foreground">{text}</p>
    </div>
  )
  if (!installation) return note("Save Play setup before running it.")
  if (installation.operatingMode === "OBSERVE" || installation.operatingMode === "RECOMMEND") {
    return note("This operating mode does not take external action. Action execution is available only after you explicitly choose an action mode.")
  }
  if (installation.operatingMode === "ACT WITHIN POLICY") {
    return note("Act within policy stays locked until effective runtime action authorization can be proven for this Play.")
  }

  return (
    <div className="rounded-[12px] border border-divide bg-[color:var(--g-surface-1)] p-4">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 text-[15px] font-semibold"><ShieldCheck className="size-4 text-[color:var(--g-emerald)]" />Run with approval</div>
          <p className="mt-1 max-w-xl text-xs leading-5 text-muted-foreground">Starts the workflows linked to this Play. Consequential actions remain in Gravitre&apos;s existing approval queue and cannot execute until approved.</p>
        </div>
        <Button onClick={runPlay} disabled={!canRun || running} aria-describedby={!canRun ? "play-run-disabled-reason" : undefined}>
          <Play className="size-4" />{running ? "Starting…" : "Run play"}
        </Button>
      </div>
      {!canRun ? <p id="play-run-disabled-reason" className="mt-3 text-xs text-muted-foreground">{disabledReason}</p> : null}
      {lastRun ? <p className="mt-3 border-t border-divide pt-3 text-xs text-muted-foreground">Play run {lastRun.id.slice(0, 8)} · {lastRun.status.replaceAll("_", " ")}</p> : null}
    </div>
  )
}
