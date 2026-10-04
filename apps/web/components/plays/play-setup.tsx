"use client"

import { useEffect, useMemo, useState } from "react"
import useSWR from "swr"
import { toast } from "sonner"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { fetcher } from "@/lib/fetcher"
import { apiFetch } from "@/lib/fetcher"
import { TYPE } from "@/lib/design-system"
import { CheckCircle2, ShieldCheck } from "lucide-react"

type Mode = "OBSERVE" | "RECOMMEND" | "ACT WITH APPROVAL" | "ACT WITHIN POLICY"
type Readiness = { observe_ready?: boolean; recommend_ready?: boolean; act_with_approval_ready?: boolean; act_within_policy_ready?: boolean }
type Goal = { id: string; objective: string; status?: string }
type Installation = { id: string; goalId?: string | null; operatingMode: Mode; status: string }

const modes: Array<{ value: Mode; title: string; description: string; readiness: keyof Readiness }> = [
  { value: "OBSERVE", title: "Observe", description: "Find opportunities and risks without recommending or taking action.", readiness: "observe_ready" },
  { value: "RECOMMEND", title: "Recommend", description: "Analyze what is happening and recommend the next best action.", readiness: "recommend_ready" },
  { value: "ACT WITH APPROVAL", title: "Act with approval", description: "Prepare consequential actions, then require a person to approve them.", readiness: "act_with_approval_ready" },
  { value: "ACT WITHIN POLICY", title: "Act within policy", description: "Execute automatically only inside configured policies and guardrails.", readiness: "act_within_policy_ready" },
]

export function PlaySetup({ playKey, playVersion, readiness }: { playKey: string; playVersion: string; readiness: Readiness }) {
  const { data, mutate } = useSWR<{ installation: Installation | null }>(`/api/plays/${playKey}/installation`, fetcher)
  const { data: goalsData } = useSWR<{ goals: Goal[] }>("/api/goals", fetcher)
  const installation = data?.installation ?? null
  const [selectedMode, setSelectedMode] = useState<Mode>("OBSERVE")
  const [goalId, setGoalId] = useState("")
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    if (!installation) return
    setSelectedMode(installation.operatingMode)
    setGoalId(installation.goalId ?? "")
  }, [installation])

  const availableModes = useMemo(() => new Set(modes.filter((item) => Boolean(readiness[item.readiness])).map((item) => item.value)), [readiness])
  const dirty = installation ? installation.operatingMode !== selectedMode || (installation.goalId ?? "") !== goalId : true

  async function save() {
    if (!availableModes.has(selectedMode)) return
    try {
      setSaving(true)
      const response = await apiFetch(`/api/plays/${playKey}/installation`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ playVersion, operatingMode: selectedMode, goalId: goalId || null, status: "ready" }),
      })
      const payload = await response.json().catch(() => ({}))
      if (!response.ok) throw new Error(typeof payload.error === "string" ? payload.error : "Could not save Play setup")
      await mutate(payload)
      toast.success("Play setup saved")
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Could not save Play setup")
    } finally {
      setSaving(false)
    }
  }

  return (
    <section className="border-y border-divide py-5">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className={TYPE.eyebrow}>Operating mode</p>
          <h2 className="mt-1 text-base font-semibold">Choose how much authority this Play has</h2>
          <p className="mt-1 text-sm text-muted-foreground">Authority increases only when the required data, workflows, approvals, and policy controls are ready.</p>
        </div>
        {installation ? <Badge variant="outline"><CheckCircle2 className="mr-1 size-3" />Configured</Badge> : null}
      </div>

      <div className="mt-5 grid gap-3 sm:grid-cols-2">
        {modes.map((item) => {
          const enabled = availableModes.has(item.value)
          const selected = selectedMode === item.value
          return (
            <button
              key={item.value}
              type="button"
              disabled={!enabled}
              aria-pressed={selected}
              aria-label={`${item.title}${enabled ? "" : " — complete readiness requirements first"}`}
              onClick={() => setSelectedMode(item.value)}
              className={`rounded-xl border p-4 text-left transition-colors ${selected ? "border-primary bg-primary/5" : "border-divide"} ${enabled ? "hover:bg-[color:var(--g-surface-2)]" : "cursor-not-allowed opacity-45"}`}
            >
              <div className="flex items-center justify-between gap-2">
                <span className="text-sm font-medium">{item.title}</span>
                {item.value.includes("ACT") ? <ShieldCheck className="size-4 text-muted-foreground" /> : null}
              </div>
              <p className="mt-2 text-xs leading-5 text-muted-foreground">{item.description}</p>
              {!enabled ? <p className="mt-2 text-xs font-medium text-warning">Complete readiness requirements first</p> : null}
            </button>
          )
        })}
      </div>

      <div className="mt-5 border-t border-divide pt-5">
        <label htmlFor="play-goal" className="text-sm font-medium">Goal</label>
        <p className="mt-1 text-xs text-muted-foreground">Optional. Link this Play to the business objective it is intended to improve.</p>
        <select id="play-goal" value={goalId} onChange={(event) => setGoalId(event.target.value)} className="mt-3 h-10 w-full rounded-md border border-input bg-background px-3 text-sm">
          <option value="">No linked goal</option>
          {(goalsData?.goals ?? []).filter((goal) => goal.status !== "cancelled").map((goal) => <option key={goal.id} value={goal.id}>{goal.objective}</option>)}
        </select>
      </div>

      <div className="mt-5 flex items-center justify-between border-t border-divide pt-4">
        <p className="text-xs text-muted-foreground">{dirty ? "Unsaved setup changes" : "Setup saved"}</p>
        <Button onClick={save} disabled={saving || !dirty || !availableModes.has(selectedMode)}>{saving ? "Saving…" : "Save setup"}</Button>
      </div>
    </section>
  )
}
