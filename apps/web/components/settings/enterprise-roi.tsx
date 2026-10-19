"use client"

/**
 * Enterprise > Agent ROI (design p18). Measured agent cost and completed tasks
 * come from GET /api/enterprise/insights/agent-roi. The hourly rate and the
 * minutes a person would spend per task are the org's own estimate inputs,
 * saved in organization settings by admins (PUT /api/enterprise/insights/agent-roi).
 * Nothing is assumed: no rate means an empty state, and agents without a
 * minutes estimate are left out of the totals and listed as such.
 */
import { useMemo, useState } from "react"
import useSWR from "swr"
import { toast } from "sonner"
import { Clock, LineChart } from "lucide-react"
import { fetcher } from "@/lib/fetcher"
import {
  agentRoiKey,
  enterpriseInsightsApi,
  formatMultiple,
  formatUsd,
  parsePositiveNumber,
  type AgentRoiSummary,
} from "@/lib/settings-api/enterprise"
import { SetError, SetNote, SetSkeleton, SetTabs } from "./settings-kit"

type Period = "7" | "30" | "90"

export function EnterpriseRoi({ isAdmin }: { isAdmin: boolean }) {
  const [period, setPeriod] = useState<Period>("30")
  const key = agentRoiKey(Number(period))
  const { data, error, isLoading, mutate } = useSWR<AgentRoiSummary>(key, fetcher, {
    revalidateOnFocus: false,
    keepPreviousData: true,
  })

  const [rateDraft, setRateDraft] = useState<string | null>(null)
  const [minutesDraft, setMinutesDraft] = useState<Record<string, string>>({})
  const [savingRate, setSavingRate] = useState(false)
  const [savingMinutes, setSavingMinutes] = useState(false)

  const savedRate = data?.laborUsdPerHour ?? null
  const rateText = rateDraft ?? (savedRate != null ? String(savedRate) : "")
  const parsedRate = parsePositiveNumber(rateText, 10_000)
  const rateDirty = rateDraft !== null && parsedRate !== savedRate

  const saveRate = async () => {
    if (!isAdmin || !rateDirty) return
    if (rateText.trim() && parsedRate == null) {
      toast.error("Enter an hourly rate above $0")
      return
    }
    setSavingRate(true)
    try {
      await enterpriseInsightsApi.updateAgentRoiInputs(parsedRate == null ? { clearRate: true } : { laborUsdPerHour: parsedRate })
      setRateDraft(null)
      await mutate()
      toast.success(parsedRate == null ? "Hourly rate cleared" : "Hourly rate saved")
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not save the rate")
    } finally {
      setSavingRate(false)
    }
  }

  const estimateAgents = useMemo(
    () => (data?.agents ?? []).filter((a) => a.tasks > 0 || a.minutesPerTask != null),
    [data?.agents],
  )
  const minuteChanges = useMemo(() => {
    const out: Record<string, number | null> = {}
    for (const agent of estimateAgents) {
      const draft = minutesDraft[agent.agentId]
      if (draft === undefined) continue
      const parsed = parsePositiveNumber(draft, 1440)
      if (draft.trim() && parsed == null) continue
      if (parsed !== agent.minutesPerTask) out[agent.agentId] = parsed
    }
    return out
  }, [estimateAgents, minutesDraft])
  const invalidMinutes = estimateAgents.some((a) => {
    const draft = minutesDraft[a.agentId]
    return draft !== undefined && draft.trim() !== "" && parsePositiveNumber(draft, 1440) == null
  })

  const saveMinutes = async () => {
    if (!isAdmin || Object.keys(minuteChanges).length === 0) return
    setSavingMinutes(true)
    try {
      await enterpriseInsightsApi.updateAgentRoiInputs({ minutesPerTask: minuteChanges })
      setMinutesDraft({})
      await mutate()
      toast.success("Minutes per task saved")
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not save the estimates")
    } finally {
      setSavingMinutes(false)
    }
  }

  const rows = data?.rows ?? []
  const vmax = Math.max(0, ...rows.map((r) => Math.max(r.laborValueUsd ?? 0, r.costUsd)))
  const totals = data?.totals

  return (
    <>
      <div className="ent-intro">
        <p>What each agent costs against the labor value of the work it finished. Set your team&apos;s hourly rate to tune the estimate.</p>
        <div className="ent-actions" style={{ alignItems: "center" }}>
          <label className="ent-rate">
            Hourly rate
            <span className="gs-input">
              <span style={{ color: "var(--gs-muted)" }}>$</span>
              <input
                type="number"
                min={1}
                max={10000}
                step="any"
                inputMode="decimal"
                aria-label="Hourly labor rate"
                placeholder="Not set"
                value={rateText}
                disabled={!isAdmin || savingRate || !data}
                onChange={(e) => setRateDraft(e.target.value)}
                onBlur={() => void saveRate()}
                onKeyDown={(e) => {
                  if (e.key === "Enter") void saveRate()
                }}
              />
            </span>
          </label>
          <SetTabs<Period>
            label="Period"
            value={period}
            onChange={setPeriod}
            options={[
              { id: "7", label: "7 days" },
              { id: "30", label: "30 days" },
              { id: "90", label: "90 days" },
            ]}
          />
        </div>
      </div>

      {error && !data ? (
        <section className="gs-card">
          <SetError message="Agent ROI did not load." onRetry={() => void mutate()} />
        </section>
      ) : isLoading && !data ? (
        <section className="gs-card">
          <SetSkeleton rows={4} label="Loading agent ROI" />
        </section>
      ) : data ? (
        <>
          {savedRate == null ? (
            <section className="gs-card">
              <div className="gs-empty">
                <LineChart size={22} aria-hidden />
                <b>Set your hourly rate</b>
                <p>
                  {isAdmin
                    ? "Enter what an hour of your team's time costs, fully loaded. Labor value is calculated from it, nothing is assumed."
                    : "An admin needs to set the team's hourly rate before labor value can be shown."}
                </p>
              </div>
            </section>
          ) : (
            <>
              <div className="gs-minis">
                <div className="gs-mini">
                  <div className="l">Agent cost</div>
                  <div className="v">{totals?.agentCostUsd == null ? "None yet" : formatUsd(totals.agentCostUsd)}</div>
                </div>
                <div className="gs-mini">
                  <div className="l">Labor value</div>
                  <div className="v" style={{ color: "var(--gs-green)" }}>
                    {totals?.laborValueUsd == null ? "None yet" : formatUsd(totals.laborValueUsd)}
                  </div>
                </div>
                <div className="gs-mini">
                  <div className="l">Net value</div>
                  <div className="v">{totals?.netValueUsd == null ? "None yet" : formatUsd(totals.netValueUsd)}</div>
                </div>
                <div className="gs-mini">
                  <div className="l">Return</div>
                  <div className="v" style={{ color: "var(--gs-green)" }}>
                    {formatMultiple(totals?.returnMultiple) ?? "None yet"}
                  </div>
                </div>
              </div>

              <section className="gs-card ent-card">
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 8 }}>
                  <h3>Cost and value by agent</h3>
                  <span className="ent-legend" style={{ marginTop: 0 }}>
                    <span>
                      <span className="gs-dot ent-c3" />
                      Cost
                    </span>
                    <span>
                      <span className="gs-dot green" />
                      Labor value
                    </span>
                  </span>
                </div>
                {rows.length === 0 ? (
                  <p className="gs-sub" style={{ marginTop: 10 }}>
                    None yet. Agents show here once they finish tasks and have minutes per task set below.
                  </p>
                ) : (
                  rows.map((row) => {
                    const multiple = row.returnMultiple
                    return (
                      <div key={row.agentId} className="ent-roi-row">
                        <div style={{ minWidth: 0 }}>
                          <div className="n">{row.name}</div>
                          <div className="d">
                            {row.tasks.toLocaleString()} tasks · {row.minutesPerTask} min each
                          </div>
                        </div>
                        <div className="ent-roi-bars">
                          <span
                            className="cost"
                            title={`Cost ${formatUsd(row.costUsd)}`}
                            style={{ width: `${vmax > 0 ? Math.max(1, (row.costUsd / vmax) * 100).toFixed(1) : 1}%` }}
                          />
                          <span
                            className="val"
                            title={`Value ${formatUsd(row.laborValueUsd)}`}
                            style={{ width: `${vmax > 0 ? Math.max(1, ((row.laborValueUsd ?? 0) / vmax) * 100).toFixed(1) : 1}%` }}
                          />
                        </div>
                        <span
                          className={`gs-mono ent-roi-x ${multiple != null && multiple >= 10 ? "green" : "amber"}`}
                          title={multiple == null ? "No measured cost in this period" : undefined}
                        >
                          {formatMultiple(multiple) ?? "No cost"}
                        </span>
                      </div>
                    )
                  })
                )}
                <div className="ent-foot-note">
                  Labor value = tasks × minutes a person would spend × hourly rate. Agents with no finished tasks are hidden.
                  {data.hiddenWithoutEstimate > 0
                    ? ` ${data.hiddenWithoutEstimate} ${data.hiddenWithoutEstimate === 1 ? "agent" : "agents"} with finished tasks ${data.hiddenWithoutEstimate === 1 ? "is" : "are"} hidden until minutes per task are set.`
                    : ""}{" "}
                  Cost is measured model spend. Labor value is an estimate from your inputs.
                </div>
              </section>
            </>
          )}

          <section className="gs-card ent-card">
            <div className="ent-title">
              <Clock size={17} aria-hidden />
              <h3>Minutes per task</h3>
            </div>
            <p className="ent-card-sub">How long a person would take to do one task each agent finishes. Used only for labor value.</p>
            {estimateAgents.length === 0 ? (
              <p className="gs-sub">None yet. Agents appear here once they finish tasks in this period.</p>
            ) : (
              <>
                {estimateAgents.map((agent) => {
                  const draft = minutesDraft[agent.agentId]
                  const value = draft ?? (agent.minutesPerTask != null ? String(agent.minutesPerTask) : "")
                  const bad = draft !== undefined && draft.trim() !== "" && parsePositiveNumber(draft, 1440) == null
                  return (
                    <div key={agent.agentId} className="ent-min-row">
                      <div style={{ minWidth: 0 }}>
                        <div className="gs-strong" style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                          {agent.name}
                        </div>
                        <div className="gs-sub">{agent.department ?? "No department"}</div>
                      </div>
                      <span className="gs-mono gs-sub">{agent.tasks.toLocaleString()} tasks</span>
                      <span className="gs-input" style={bad ? { borderColor: "var(--gs-red)" } : undefined}>
                        <input
                          type="number"
                          min={0}
                          max={1440}
                          step="any"
                          inputMode="decimal"
                          placeholder="Not set"
                          aria-label={`Minutes per task for ${agent.name}`}
                          aria-invalid={bad}
                          value={value}
                          disabled={!isAdmin || savingMinutes}
                          onChange={(e) => setMinutesDraft((d) => ({ ...d, [agent.agentId]: e.target.value }))}
                        />
                        <span style={{ color: "var(--gs-muted)", fontSize: 12 }}>min</span>
                      </span>
                    </div>
                  )
                })}
                {isAdmin ? (
                  <div style={{ display: "flex", justifyContent: "flex-end", marginTop: 12 }}>
                    <button
                      type="button"
                      className="gs-btn dark sm"
                      disabled={savingMinutes || invalidMinutes || Object.keys(minuteChanges).length === 0}
                      onClick={() => void saveMinutes()}
                    >
                      {savingMinutes ? "Saving…" : "Save estimates"}
                    </button>
                  </div>
                ) : null}
              </>
            )}
          </section>
          {!isAdmin ? <SetNote>Only workspace admins can change the hourly rate and minutes per task.</SetNote> : null}
        </>
      ) : null}
    </>
  )
}
