"use client"

/**
 * Verified Play impact and Play readiness, shown under the Reports board in the v3 card style.
 * Both render only when the workspace has Plays data, so an empty workspace sees the board alone.
 * Impact counts business results confirmed by a source of record, never workflow completion.
 */

import Link from "next/link"
import useSWR from "swr"
import { playsApi, type PlayListItem } from "@/lib/api"
import { APP_ROUTES } from "@/lib/app-routes"
import type { ReportsRange } from "@/lib/dashboard/home-reports"

const QUIET = { revalidateOnFocus: false, shouldRetryOnError: false, refreshInterval: 60_000 } as const
const PLAYS_PREVIEW = 3

export function playState(readiness: PlayListItem["readiness"]): { label: string; ready: boolean } {
  if (readiness.act_within_policy_ready) return { label: "Act within policy", ready: true }
  if (readiness.act_with_approval_ready) return { label: "Act with approval", ready: true }
  if (readiness.recommend_ready) return { label: "Ready to recommend", ready: true }
  if (readiness.observe_ready) return { label: "Ready to observe", ready: true }
  if (readiness.dependency_status === "EXTERNAL_CONNECTION_REQUIRED") return { label: "Setup required", ready: false }
  return { label: "Needs attention", ready: false }
}

const label = { fontSize: 13, color: "var(--gv-muted)" } as const
const big = { fontSize: 26, fontWeight: 600, letterSpacing: "-0.02em", fontVariantNumeric: "tabular-nums" } as const

export function PlayOutcomes({ enabled, range }: { enabled: boolean; range: ReportsRange }) {
  const impact = useSWR(enabled ? `home/play-impact:${range}` : null, () => playsApi.impact(range), QUIET)
  const plays = useSWR(enabled ? "home/plays" : null, () => playsApi.list(), QUIET)
  const summary = impact.data
  const list = plays.data?.plays ?? []
  const showImpact = Boolean(summary && (summary.verifiedResultCount > 0 || summary.pendingVerificationCount > 0))
  if (!showImpact && list.length === 0) return null
  const ready = list.filter(({ readiness }) => playState(readiness).ready).length

  return (
    <div className="gv-grid" style={{ marginTop: 16 }}>
      {showImpact && summary ? (
        <section className="gv-card gv-w" style={{ gridColumn: "span 2", padding: 20 }} aria-labelledby="home-play-impact">
          <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 12 }}>
            <div>
              <h3 id="home-play-impact" style={{ margin: 0, fontSize: 15, fontWeight: 600 }}>Verified Play impact</h3>
              <div style={{ ...label, marginTop: 4 }}>
                Business results confirmed by a source of record. Workflow completion is not counted as impact.
              </div>
            </div>
            <Link href={APP_ROUTES.plays} className="gv-btn text" style={{ fontSize: 13 }}>View plays →</Link>
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(3, minmax(0, 1fr))", gap: 16, marginTop: 18 }}>
            <div>
              <div style={label}>Verified results</div>
              <div style={big}>{summary.verifiedResultCount}</div>
            </div>
            <div>
              <div style={label}>Pending verification</div>
              <div style={big}>{summary.pendingVerificationCount}</div>
            </div>
            <div>
              <div style={label}>Verified measured impact</div>
              {summary.verifiedMetrics.length ? (
                summary.verifiedMetrics.slice(0, 2).map((m) => (
                  <div key={`${m.metricKey}-${m.currency ?? ""}`} style={{ fontSize: 14, fontWeight: 600, marginTop: 4 }}>
                    {m.currency ? `${m.currency} ` : ""}
                    {m.value.toLocaleString()} <span style={{ fontWeight: 400, color: "var(--gv-muted)" }}>{m.metricKey.replaceAll("_", " ")}</span>
                  </div>
                ))
              ) : (
                <div style={{ fontSize: 14, color: "var(--gv-muted)", marginTop: 4 }}>No verified measured change yet</div>
              )}
            </div>
          </div>
        </section>
      ) : null}

      {list.length > 0 ? (
        <section className="gv-card gv-w" style={{ gridColumn: showImpact ? "span 2" : "span 4", padding: 20 }} aria-labelledby="home-outcome-plays">
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12 }}>
            <h3 id="home-outcome-plays" style={{ margin: 0, fontSize: 15, fontWeight: 600 }}>
              Outcome plays <span className="gv-chip" style={{ marginLeft: 6 }}>{ready} of {list.length} ready</span>
            </h3>
            <Link href={APP_ROUTES.plays} className="gv-btn text" style={{ fontSize: 13 }}>
              {list.length > PLAYS_PREVIEW ? `View all ${list.length} →` : "View plays →"}
            </Link>
          </div>
          <ul style={{ listStyle: "none", margin: "12px 0 0", padding: 0 }}>
            {list.slice(0, PLAYS_PREVIEW).map(({ play, readiness, workflowBindingCount }) => {
              const state = playState(readiness)
              return (
                <li key={play.key} className="gv-row" style={{ display: "flex", alignItems: "center", gap: 12, padding: "10px 0", borderTop: "1px solid var(--gv-border)" }}>
                  <div style={{ minWidth: 0, flex: 1 }}>
                    <div style={{ fontSize: 14, fontWeight: 500 }}>{play.name}</div>
                    <div style={{ ...label, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                      {workflowBindingCount > 0
                        ? `${workflowBindingCount} canonical workflow${workflowBindingCount === 1 ? "" : "s"} bound`
                        : "No canonical workflow bound yet"}
                    </div>
                  </div>
                  <span style={{ display: "inline-flex", alignItems: "center", gap: 6, fontSize: 12, fontWeight: 500, color: state.ready ? "#0E8A55" : "var(--gv-muted)" }}>
                    <span aria-hidden style={{ width: 6, height: 6, borderRadius: 999, background: state.ready ? "#19C37D" : "#E2A33A" }} />
                    {state.label}
                  </span>
                </li>
              )
            })}
          </ul>
        </section>
      ) : null}
    </div>
  )
}
