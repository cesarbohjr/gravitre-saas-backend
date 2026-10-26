import { useState } from "react"
import { policyLine } from "@web/components/approvals/decision-queue/model"
import { useStore } from "../store"
import { AgentAvatar, ErrorLine, Icon, Logo, MOD, Section } from "../ui"
import { age, clock, dayLabel, greeting, percentDone, progressLine, systemBadge } from "../lib/model"
import { identityOf } from "../lib/identity"
import { AgentChip, ModeSwitch } from "../components/Composer"

export const STARTERS = [
  "What changed since yesterday?",
  "What needs my approval?",
  "What's blocked right now?",
  "Summarize this week's results",
]

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="card" style={{ padding: "14px 16px", display: "flex", flexDirection: "column", gap: 2 }}>
      <span className="sub">{label}</span>
      <span className="mono" style={{ fontSize: 24, fontWeight: 600 }}>
        {value}
      </span>
    </div>
  )
}

export function Home() {
  const { me, agents, approvals, assignments, totals, go, web, setOverlay } = useStore()
  const [draft, setDraft] = useState("")

  const jobs = assignments.data
  const running = jobs.filter((a) => a.status === "running")
  const inProgress = jobs.filter((a) => a.status === "running" || a.status === "waiting").slice(0, 4)
  const blocked = jobs.filter((a) => a.status === "failed").slice(0, 2)
  const results = jobs.filter((a) => a.status === "done").slice(0, 3)
  const loaded = approvals.at != null && assignments.at != null

  const waiting = [
    ...approvals.data.slice(0, 4).map((a) => ({
      key: a.id,
      who: identityOf(agents, a.requestedBy),
      title: a.title,
      meta: [a.requestedBy, policyLine(a), age(a.requestedAt)].filter(Boolean).join(" · "),
      system: systemBadge(a.context.integration),
      action: "Review",
      run: () => go({ view: "appr", select: a.id }),
    })),
    ...blocked.map((a) => ({
      key: a.id,
      who: identityOf(agents, a.agent, a.agentId),
      title: `${a.title} is blocked`,
      meta: [a.agent, a.outcome].filter(Boolean).join(" · "),
      system: a.steps.find((s) => s.state === "failed")?.system || "",
      action: "Fix on web ↗",
      run: () => web(`/assignments/${encodeURIComponent(a.id)}`),
    })),
  ]
  const nWaiting = approvals.data.length

  const ask = (text: string) => {
    const t = text.trim()
    if (!t) return
    setDraft("")
    go({ view: "ask", ask: t, select: null })
  }

  const today = new Date().toLocaleDateString(undefined, { weekday: "long", month: "long", day: "numeric" })
  const num = (v: number | null) => (v == null ? "–" : String(v))

  return (
    <div className="scroll fade" style={{ flex: 1 }}>
      <div className="hdr">
        <div style={{ flex: 1, display: "flex", flexDirection: "column" }}>
          <h1>{greeting(me?.name)}</h1>
          <span className="sub">{today}</span>
        </div>
        <button className="cmd" onClick={() => setOverlay("cmd")}>
          <Icon name="search" />
          <span style={{ flex: 1, textAlign: "left" }}>Search or jump to</span>
          <span className="kbd">{MOD} K</span>
        </button>
      </div>
      <div style={{ padding: "12px 24px 24px", display: "flex", flexDirection: "column", gap: 16 }}>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(3, minmax(0, 1fr))", gap: 12 }}>
          <Stat label="Hours saved this week" value={num(totals.data.hoursSaved)} />
          <Stat label="Tasks completed this week" value={num(totals.data.completed)} />
          <Stat label="Assignments running now" value={assignments.at ? String(running.length) : "–"} />
        </div>
        {approvals.error && !approvals.at ? <ErrorLine message={approvals.error} /> : null}
        <div style={{ display: "grid", gridTemplateColumns: "minmax(0, 1.55fr) minmax(0, 1fr)", gap: 16, alignItems: "start" }}>
          <div style={{ display: "flex", flexDirection: "column", gap: 16, minWidth: 0 }}>
            <Section
              title="Waiting for you"
              count={nWaiting}
              action={
                <button className="mlink" onClick={() => go("appr")}>
                  All approvals
                </button>
              }
            >
              {waiting.length === 0 ? (
                <div className="rw sub">{loaded ? "Nothing needs you. New requests show here the moment an agent pauses." : "Loading…"}</div>
              ) : (
                waiting.map((w) => (
                  <div key={w.key} className="rw">
                    <AgentAvatar id={w.who} />
                    <div style={{ flex: 1, minWidth: 0, display: "flex", flexDirection: "column" }}>
                      <span className="ell" style={{ fontSize: 14, fontWeight: 500 }}>
                        {w.title}
                      </span>
                      <span className="sub ell">{w.meta}</span>
                    </div>
                    <Logo text={w.system} />
                    <button className="btn btn-sm" onClick={w.run}>
                      {w.action}
                    </button>
                  </div>
                ))
              )}
            </Section>
            <Section
              title="In progress"
              action={
                <button className="mlink" onClick={() => go("assign")}>
                  All assignments
                </button>
              }
            >
              {inProgress.length === 0 ? (
                <div className="rw sub">{assignments.at ? "Nothing is running right now." : "Loading…"}</div>
              ) : (
                inProgress.map((a) => (
                  <button key={a.id} className="rw rwb" onClick={() => go({ view: "assign", select: a.id })}>
                    <AgentAvatar id={identityOf(agents, a.agent, a.agentId)} />
                    <div style={{ flex: 1, minWidth: 0, display: "flex", flexDirection: "column", gap: 6 }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                        <span className="ell" style={{ fontSize: 14, fontWeight: 500, flex: 1 }}>
                          {a.title}
                        </span>
                        <span className="sub">{progressLine(a)}</span>
                      </div>
                      {percentDone(a) != null ? (
                        <div className="bar">
                          <i style={{ width: `${percentDone(a)}%` }} />
                        </div>
                      ) : null}
                    </div>
                  </button>
                ))
              )}
            </Section>
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 16, minWidth: 0 }}>
            <section className="card" style={{ padding: 12, display: "flex", flexDirection: "column", gap: 10 }}>
              <h2 style={{ margin: 0, fontSize: 14, fontWeight: 600, padding: "0 2px" }}>Ask anything</h2>
              <div className="composer">
                <label htmlFor="home-ask" className="sr">
                  Ask anything
                </label>
                <textarea
                  id="home-ask"
                  className="ta"
                  rows={2}
                  placeholder="What changed in my pipeline since Monday?"
                  value={draft}
                  onChange={(e) => setDraft(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && !e.shiftKey) {
                      e.preventDefault()
                      ask(draft)
                    }
                  }}
                />
                <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                  <AgentChip />
                  <span style={{ flex: 1 }} />
                  <ModeSwitch onVoice={() => go("voice")} />
                  <button className="ib send" aria-label="Ask" disabled={!draft.trim()} onClick={() => ask(draft)}>
                    <Icon name="up" size={15} strokeWidth={2} />
                  </button>
                </div>
              </div>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
                {STARTERS.slice(0, 2).map((t) => (
                  <button key={t} className="btn btn-sm" style={{ borderRadius: 14 }} onClick={() => ask(t)}>
                    {t}
                  </button>
                ))}
              </div>
            </section>
            <Section
              title="Recent results"
              action={
                <button className="mlink" onClick={() => web("/assignments")}>
                  Results on web ↗
                </button>
              }
            >
              {results.length === 0 ? (
                <div className="rw sub">{assignments.at ? "Finished assignments show here." : "Loading…"}</div>
              ) : (
                results.map((r) => (
                  <div key={r.id} className="rw" style={{ alignItems: "flex-start" }}>
                    <Icon name="checkc" style={{ color: "var(--ok)", marginTop: 2 }} />
                    <div style={{ flex: 1, minWidth: 0, display: "flex", flexDirection: "column" }}>
                      <span className="ell" style={{ fontSize: 13, fontWeight: 500 }}>
                        {r.outcome && r.outcome !== "Finished." ? r.outcome : r.title}
                      </span>
                      <span className="sub ell">
                        {[r.agent, r.outcome && r.outcome !== "Finished." ? r.title : null, dayLabel(r.finishedAt || r.createdAt) === "Today" ? clock(r.finishedAt || r.createdAt) : dayLabel(r.finishedAt || r.createdAt)]
                          .filter(Boolean)
                          .join(" · ")}
                      </span>
                    </div>
                    <button className="link" onClick={() => web(`/assignments/${encodeURIComponent(r.id)}`)}>
                      Open
                    </button>
                  </div>
                ))
              )}
            </Section>
          </div>
        </div>
      </div>
    </div>
  )
}
