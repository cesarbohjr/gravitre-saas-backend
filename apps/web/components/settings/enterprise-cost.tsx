"use client"

/**
 * Enterprise > Cost attribution (design p18): month-to-date measured spend
 * from GET /api/enterprise/insights/cost (model_calls.cost_usd, usage_events
 * fallback), grouped by department or by agent.
 */
import { useState } from "react"
import useSWR from "swr"
import { DollarSign } from "lucide-react"
import { fetcher } from "@/lib/fetcher"
import { COST_KEY, costShares, formatUsd, type CostAttributionSummary } from "@/lib/settings-api/enterprise"
import { SetError, SetSkeleton, SetTabs } from "./settings-kit"

type Group = "dept" | "agent"
const COLORS = ["ent-c0", "ent-c1", "ent-c2", "ent-c3", "ent-c4", "ent-c5"]

export function EnterpriseCost() {
  const [group, setGroup] = useState<Group>("dept")
  const { data, error, isLoading, mutate } = useSWR<CostAttributionSummary>(COST_KEY, fetcher, { revalidateOnFocus: false })

  const rows = data ? (group === "dept" ? data.byDepartment : data.byAgent) : []
  const shared = costShares(rows, data?.totalCostUsd ?? 0)
  const hasCost = Boolean(data && data.totalCostUsd > 0)

  return (
    <>
      <div className="ent-intro">
        <p>Where this month&apos;s AI and run spend went.</p>
        <SetTabs<Group>
          label="Group by"
          value={group}
          onChange={setGroup}
          options={[
            { id: "dept", label: "By department" },
            { id: "agent", label: "By agent" },
          ]}
        />
      </div>

      {error && !data ? (
        <section className="gs-card">
          <SetError message="Cost data did not load." onRetry={() => void mutate()} />
        </section>
      ) : isLoading || !data ? (
        <section className="gs-card">
          <SetSkeleton rows={4} label="Loading cost attribution" />
        </section>
      ) : !hasCost ? (
        <section className="gs-card">
          <div className="gs-empty">
            <DollarSign size={22} aria-hidden />
            <b>None yet</b>
            <p>No measured model or run spend has been recorded this month. Spend shows here as agents and workflows run.</p>
          </div>
        </section>
      ) : (
        <>
          <section className="gs-card" style={{ padding: 20 }}>
            <div className="ent-total">
              <b>{formatUsd(data.totalCostUsd)}</b>
              <span>
                spent this period across {data.agentCount} {data.agentCount === 1 ? "agent" : "agents"}
              </span>
            </div>
            <div className="ent-stack" aria-hidden>
              {shared.map((row, i) => (
                <span
                  key={row.id}
                  className={COLORS[Math.min(i, COLORS.length - 1)]}
                  style={{ width: `${row.sharePct.toFixed(1)}%`, animationDelay: `${i * 80}ms` }}
                />
              ))}
            </div>
            <div className="ent-legend">
              {shared.map((row, i) => (
                <span key={row.id}>
                  <span className={`gs-dot ${COLORS[Math.min(i, COLORS.length - 1)]}`} />
                  {row.name}
                </span>
              ))}
            </div>
          </section>

          <section className="gs-card clip">
            <div className="gs-scroll-x">
              <div className="gs-tbl stack" style={{ ["--cols" as string]: "minmax(160px,1fr) 90px 100px 140px" }}>
                <div className="gs-tr head" style={{ background: "var(--gs-band)" }}>
                  <div className="gs-th">{group === "dept" ? "Department" : "Agent"}</div>
                  <div className="gs-th">Runs</div>
                  <div className="gs-th">Cost</div>
                  <div className="gs-th">Share</div>
                </div>
                {shared.map((row, i) => (
                  <div key={row.id} className="gs-row">
                    <div className="gs-td" style={{ display: "flex", gap: 10, alignItems: "center" }}>
                      <span className={`gs-dot ${COLORS[Math.min(i, COLORS.length - 1)]}`} style={{ width: 9, height: 9 }} />
                      <div style={{ minWidth: 0 }}>
                        <div className="t">{row.name}</div>
                        <div className="s">
                          {group === "dept"
                            ? `${row.agentCount ?? 0} ${(row.agentCount ?? 0) === 1 ? "agent" : "agents"}`
                            : row.department ?? "No department"}
                          {` · ${row.calls.toLocaleString()} model ${row.calls === 1 ? "call" : "calls"}`}
                        </div>
                      </div>
                    </div>
                    <div className="gs-td gs-mono" style={{ fontSize: 13 }} title="Distinct runs linked to this spend">
                      {row.runs.toLocaleString()}
                    </div>
                    <div className="gs-td gs-mono" style={{ fontSize: 13 }}>
                      {formatUsd(row.costUsd)}
                    </div>
                    <div className="gs-td">
                      <span className="ent-share">
                        <span className="gs-track">
                          <span className={COLORS[Math.min(i, COLORS.length - 1)]} style={{ width: `${row.sharePct.toFixed(1)}%` }} />
                        </span>
                        <span className="gs-mono">{Math.round(row.sharePct)}%</span>
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
            <div className="gs-foot">
              <span>
                Measured from {data.source === "usage_events" ? "usage events" : "model call costs"} since{" "}
                {new Date(data.periodStart).toLocaleDateString(undefined, { month: "short", day: "numeric" })}. Runs counts
                distinct runs linked to the spend.
              </span>
            </div>
          </section>
        </>
      )}
    </>
  )
}
