"use client"

import { useState } from "react"
import Link from "next/link"
import useSWR from "swr"
import { useAuth } from "@/lib/auth-context"
import { listAudit, rangeStart } from "@/lib/settings-api/audit"
import { eventActor, eventTitle, isErrorEvent } from "@/components/settings/audit-model"
import { Hero, Icon, Note, Pill, Segmented, Switch } from "./ts-ui"

type Threshold = "all" | "med" | "high"
type Sla = "1h" | "4h" | "8h" | "24h"
type Channel = "email" | "slack" | "app"

const THR: Record<Threshold, string> = { all: "All", med: "Med and high", high: "High only" }
const SLAS: Record<Sla, string> = { "1h": "1 hour", "4h": "4 hours", "8h": "8 hours", "24h": "24 hours" }
const CHANNELS: Array<[Channel, string]> = [["email", "Email"], ["slack", "Slack"], ["app", "In app"]]

/** Guardrail switches for the Policies tab; the page reads `on` for the tab badge. */
export function usePolicyState() {
  const [p1, setP1] = useState(true)
  const [p2, setP2] = useState(true)
  const [p3, setP3] = useState(false)
  const [p4, setP4] = useState(true)
  const [thr, setThr] = useState<Threshold>("all")
  const [sla, setSla] = useState<Sla>("4h")
  const [slaAct, setSlaAct] = useState("escalate")
  const [chans, setChans] = useState<Record<Channel, boolean>>({ email: true, slack: false, app: true })
  const on = [p1, p2, p3, p4].filter(Boolean).length
  return { p1, setP1, p2, setP2, p3, setP3, p4, setP4, thr, setThr, sla, setSla, slaAct, setSlaAct, chans, setChans, on }
}

export type PolicyState = ReturnType<typeof usePolicyState>

function shortTime(iso: string): string {
  const d = new Date(iso)
  return Number.isNaN(d.getTime()) ? "" : d.toLocaleString(undefined, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" })
}

export function TrustSafetyPolicies({ state, onOpenAudit }: { state: PolicyState; onOpenAudit: () => void }) {
  const { user } = useAuth()
  const s = state
  const recent = useSWR(user ? (["trust-safety/policies/recent", user.id] as const) : null, () =>
    listAudit({ range: "30d", category: "setting" }, rangeStart("30d"), { limit: 2, offset: 0 }),
  { revalidateOnFocus: false })
  const changes = (recent.data?.logs ?? []).slice(0, 2)

  const chanCount = Object.values(s.chans).filter(Boolean).length
  const advice =
    s.on >= 4
      ? "Every guardrail is on. Agents stop and ask before anything risky."
      : !s.p1
        ? "Turn on approval for writes so no agent changes data without a human."
        : !s.p3
          ? "Turn on high risk alerts so admins hear about destructive actions right away."
          : "Turn the remaining guardrails on for full coverage."

  return (
    <>
      <Hero
        art="policies"
        eyebrow="Policies · guardrail coverage"
        big={s.on}
        unit="of 4 policies on"
        bars={[0, 1, 2, 3].map((i) => i < s.on)}
        advice={advice}
        actions={
          <Link href="/settings/approvals" className="ts-btn green sm">
            <Icon name="plus" size={15} width={2} />
            New policy
          </Link>
        }
        tiles={[
          { value: `${s.on} of 4`, label: "Policies on", tone: "good" },
          { value: s.p1 ? THR[s.thr] : "Off", label: "Writes guarded" },
          { value: s.p2 ? SLAS[s.sla] : "Off", label: "SLA window" },
          { value: s.p3 ? chanCount : 0, label: "Alert channels" },
        ]}
      />
      <div className="ts-cols">
        <div className="ts-colmain">
          <section className="ts-card" style={{ overflow: "hidden" }}>
            <div className="ts-cardhead">
              <div style={{ flex: "1 1 200px", minWidth: 0 }}>
                <div style={{ fontWeight: 600 }}>Approval policies</div>
                <div style={{ fontSize: 13, color: "#6A6B64", marginTop: 2 }}>Applied to every agent, workflow and chat write</div>
              </div>
            </div>
            <div className="ts-sec">
              <span className="ts-ico"><Icon name="shield" /></span>
              <div style={{ flex: "1 1 260px", minWidth: 0 }}>
                <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
                  <span style={{ fontWeight: 600 }}>Require approval for writes</span>
                  <span className="ts-chip ts-mono" style={{ cursor: "default", minHeight: 22, fontSize: 11 }}>write-guard</span>
                </div>
                <div style={{ fontSize: 13, color: "#6A6B64", marginTop: 2 }}>Agents pause and wait for a human decision before any write action</div>
              </div>
              <Switch on={s.p1} label="Require approval for writes" onToggle={() => s.setP1((v) => !v)} />
              {s.p1 ? (
                <div className="ts-sub">
                  <span style={{ fontSize: 13, color: "#6A6B64" }}>Applies to</span>
                  <Segmented label="Write risk threshold" value={s.thr} onChange={s.setThr} options={[["all", "All writes"], ["med", "Medium and high"], ["high", "High only"]] as const} />
                </div>
              ) : null}
            </div>
            <div className="ts-sec">
              <span className="ts-ico"><Icon name="clock" /></span>
              <div style={{ flex: "1 1 260px", minWidth: 0 }}>
                <div style={{ fontWeight: 600 }}>SLA timeout</div>
                <div style={{ fontSize: 13, color: "#6A6B64", marginTop: 2 }}>Decisions not made inside the window are escalated or rejected</div>
              </div>
              <Switch on={s.p2} label="SLA timeout" onToggle={() => s.setP2((v) => !v)} />
              {s.p2 ? (
                <div className="ts-sub">
                  <span style={{ fontSize: 13, color: "#6A6B64" }}>After</span>
                  <select className="ts-select sm" aria-label="SLA window" value={s.sla} onChange={(e) => s.setSla(e.target.value as Sla)}>
                    {(Object.keys(SLAS) as Sla[]).map((k) => <option key={k} value={k}>{SLAS[k]}</option>)}
                  </select>
                  <span style={{ fontSize: 13, color: "#6A6B64" }}>then</span>
                  <select className="ts-select sm" aria-label="SLA action" value={s.slaAct} onChange={(e) => s.setSlaAct(e.target.value)}>
                    <option value="escalate">Escalate to owners</option>
                    <option value="reject">Reject automatically</option>
                  </select>
                </div>
              ) : null}
            </div>
            <div className="ts-sec">
              <span className={s.p3 ? "ts-ico" : "ts-ico warn"}><Icon name="warn" /></span>
              <div style={{ flex: "1 1 260px", minWidth: 0 }}>
                <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
                  <span style={{ fontWeight: 600 }}>Notify on high risk actions</span>
                  {!s.p3 ? <Pill bg="#FBF1DC" fg="#8A5A06" dot="#E2A33A">Recommended</Pill> : null}
                </div>
                <div style={{ fontSize: 13, color: "#6A6B64", marginTop: 2 }}>Alert admins when an agent tries a destructive or irreversible operation</div>
              </div>
              <Switch on={s.p3} label="Notify on high risk actions" onToggle={() => s.setP3((v) => !v)} />
              {s.p3 ? (
                <div className="ts-sub">
                  <span style={{ fontSize: 13, color: "#6A6B64" }}>Send to</span>
                  {CHANNELS.map(([id, label]) => (
                    <button
                      key={id}
                      type="button"
                      className={`ts-chip${s.chans[id] ? " on" : ""}`}
                      aria-pressed={s.chans[id]}
                      onClick={() => s.setChans((c) => ({ ...c, [id]: !c[id] }))}
                    >
                      {label}
                    </button>
                  ))}
                </div>
              ) : null}
            </div>
            <div className="ts-sec">
              <span className="ts-ico"><Icon name="lock" /></span>
              <div style={{ flex: "1 1 260px", minWidth: 0 }}>
                <div style={{ fontWeight: 600 }}>Lock agent scope per run</div>
                <div style={{ fontSize: 13, color: "#6A6B64", marginTop: 2 }}>Agents cannot reach connectors outside their assigned run context</div>
              </div>
              <Switch on={s.p4} label="Lock agent scope per run" onToggle={() => s.setP4((v) => !v)} />
            </div>
          </section>
        </div>
        <aside className="ts-colside" aria-label="Recent policy activity">
          <section className="ts-card ts-side">
            <div className="ts-sidetitle"><span className="ts-ico sm warn"><Icon name="clock" size={15} /></span>Recent changes</div>
            {changes.length === 0 ? (
              <div className="ts-mini" style={{ fontSize: 13, color: "#6A6B64" }}>{recent.data ? "No setting changes in the last 30 days." : "Loading recent changes."}</div>
            ) : (
              changes.map((log) => (
                <div key={log.id} className="ts-mini">
                  <span className="ts-dot" style={{ background: isErrorEvent(log) ? "#C4434F" : "#E2A33A" }} />
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontSize: 14, fontWeight: 500 }}>{eventTitle(log)}</div>
                    <div style={{ fontSize: 12, color: "#6A6B64" }}>{eventActor(log)} · {shortTime(log.created_at)}</div>
                  </div>
                </div>
              ))
            )}
            <button type="button" className="ts-btn text sm" style={{ alignSelf: "flex-start", padding: "0 4px" }} onClick={onOpenAudit}>Open audit trail</button>
          </section>
          <Note>Policies apply organization wide and every change is recorded.</Note>
        </aside>
      </div>
    </>
  )
}
