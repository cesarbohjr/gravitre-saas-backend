import { useState } from "react"
import { useStore } from "../store"
import { Art, Avatar, Card, ErrorLine, Icon, Live, StatusPill } from "../ui"
import { ART } from "../art"
import { clock, timeAgo } from "../lib/model"
import { policyLine } from "@web/components/approvals/decision-queue/model"

export const STARTERS = [
  "What changed since yesterday?",
  "What needs my approval?",
  "What's blocked right now?",
  "Summarize this week's results",
]

function greeting(name: string | undefined) {
  const h = new Date().getHours()
  const part = h < 12 ? "Good morning" : h < 18 ? "Good afternoon" : "Good evening"
  const first = (name || "").split(" ")[0]
  return first ? `${part}, ${first}` : part
}

export function Home() {
  const { me, approvals, assignments, totals, go, web } = useStore()
  const [draft, setDraft] = useState("")

  const pending = approvals.data
  const jobs = assignments.data
  const waitingJobs = jobs.filter((a) => a.status === "waiting")
  const failed = jobs.filter((a) => a.status === "failed").slice(0, 2)
  const running = jobs.filter((a) => a.status === "running")
  const nDec = pending.length + waitingJobs.length
  const nRun = running.length
  const loaded = approvals.at != null && assignments.at != null

  const bars: string[] = []
  for (let i = 0; i < Math.min(nDec, 4); i++) bars.push("#e2a33a")
  for (let i = 0; i < Math.min(nRun, 3); i++) bars.push("#cfe9dd")
  if (!bars.length) bars.push("#cfe9dd")

  const ask = (text: string) => {
    const t = text.trim()
    if (!t) return
    setDraft("")
    go({ view: "ask", ask: t, select: null })
  }

  const runWord = (n: number) => `${n} assignment${n === 1 ? " is" : "s are"} running.`
  const lede = !loaded
    ? "Checking what's waiting on you…"
    : nDec
      ? `${nDec === 1 ? "One request is" : `${nDec} requests are`} paused for your approval. ${runWord(nRun)}`
      : `${runWord(nRun)} You'll get a notification when anything needs you.`

  const waitingRows = [
    ...pending.slice(0, 3).map((a) => ({
      key: a.id,
      name: a.requestedBy,
      title: a.title,
      meta: [a.requestedBy, policyLine(a), timeAgo(a.requestedAt)].filter(Boolean).join(" · "),
      action: "Review",
      open: () => go({ view: "appr", select: a.id }),
    })),
    ...waitingJobs.slice(0, 2).map((a) => ({
      key: a.id,
      name: a.agent,
      title: a.title,
      meta: [a.agent, a.approvalPrompt || "Waiting on a decision", timeAgo(a.createdAt)].filter(Boolean).join(" · "),
      action: "Review",
      open: () => go({ view: "assign", select: a.id }),
    })),
    ...failed.map((a) => ({
      key: a.id,
      name: a.agent,
      title: `${a.title} is blocked`,
      meta: [a.agent, a.outcome].filter(Boolean).join(" · "),
      action: "Open",
      open: () => go({ view: "assign", select: a.id }),
    })),
  ]

  const inProgress = jobs.filter((a) => a.status === "running" || a.status === "waiting").slice(0, 4)
  const results = jobs.filter((a) => a.status === "done").slice(0, 3)

  return (
    <div className="page fade">
      <div style={{ display: "flex", alignItems: "center", gap: 16, paddingBottom: 18, borderBottom: "1px solid var(--bd)" }}>
        <h1 className="h1" style={{ fontSize: 28 }}>
          Home
        </h1>
        <span style={{ flex: 1 }} />
        <Live at={approvals.at} />
      </div>
      <div className="hero">
      <div style={{ display: "flex", flexDirection: "column", gap: 14, padding: "18px 0 6px", minWidth: 0 }}>
        <span className="eyebrow">{greeting(me?.name)}</span>
        <h2 style={{ margin: 0, fontSize: 44, fontWeight: 600, letterSpacing: "-0.025em", lineHeight: 1.05 }}>
          {!loaded ? (
            <span style={{ color: "var(--t3)" }}>Loading…</span>
          ) : nDec === 0 ? (
            <>
              <span style={{ color: "var(--ochre)" }}>All clear.</span> Nothing needs you.
            </>
          ) : (
            <>
              <span style={{ color: "var(--ochre)" }}>{nDec === 1 ? "1 decision" : `${nDec} decisions`}</span>{" "}
              {nDec === 1 ? "needs you." : "need you."}
            </>
          )}
        </h2>
        <p className="lede">{lede}</p>
        <div style={{ display: "flex", gap: 6, maxWidth: 628, marginTop: 8 }}>
          {bars.map((c, i) => (
            <span key={i} style={{ flex: 1, height: 10, borderRadius: 3, background: c }} />
          ))}
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 18, fontSize: 13, color: "var(--t2)" }}>
          <span style={{ display: "inline-flex", alignItems: "center", gap: 8 }}>
            <span style={{ width: 9, height: 9, borderRadius: 2, background: "#e2a33a" }} />
            <b style={{ color: "var(--t1)" }}>{nDec}</b> waiting
          </span>
          <span style={{ display: "inline-flex", alignItems: "center", gap: 8 }}>
            <span style={{ width: 9, height: 9, borderRadius: 2, background: "#cfe9dd" }} />
            <b style={{ color: "var(--t1)" }}>{nRun}</b> running
          </span>
          <button className="btn btn-l btn-sm" onClick={() => go("appr")}>
            Review approvals →
          </button>
        </div>
      </div>
      <div className="hero-art" aria-hidden="true">
        <Art src={nDec === 0 && loaded ? ART.siteHealth : ART.pipeline} width={400} float style={{ width: "100%" }} />
        {loaded ? (
          <div className="hero-chips">
            {nDec ? (
              <span className="hero-chip">
                <span className="cdot ping" style={{ background: "#e2a33a" }} />
                {nDec} waiting on you
              </span>
            ) : null}
            <span className="hero-chip">
              <span className={`cdot ${nRun ? "ping" : ""}`} style={{ background: nRun ? "#19c37d" : "#9aa29d" }} />
              {nRun ? `${nRun} running` : "Agents idle"}
            </span>
          </div>
        ) : null}
      </div>
      </div>
      <div className="askbar">
        <Icon name="spark" size={20} style={{ color: "var(--ok)" }} />
        <label htmlFor="home-ask" className="sr">
          Ask Gravitre
        </label>
        <input
          id="home-ask"
          placeholder="Ask Gravitre anything about your agents, runs or pipeline"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") ask(draft)
          }}
        />
        <div className="mode" role="radiogroup" aria-label="Conversation mode">
          <button className="on" role="radio" aria-checked="true">
            <Icon name="ask" size={14} />
            Text
          </button>
          <button role="radio" aria-checked="false" onClick={() => go("voice")}>
            <Icon name="voice" size={14} />
            Voice
          </button>
        </div>
        <button className="btn btn-k" style={{ height: 48, padding: "0 18px", fontSize: 14 }} onClick={() => ask(draft)}>
          Ask <span style={{ opacity: 0.6 }}>↵</span>
        </button>
      </div>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 10 }}>
        {STARTERS.map((t) => (
          <button key={t} className="qchip" onClick={() => ask(t)}>
            <span style={{ color: "var(--br)" }}>↳</span>
            {t}
          </button>
        ))}
      </div>
      {approvals.error && !approvals.at ? <ErrorLine message={approvals.error} /> : null}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(min(340px, 100%), 1fr))", gap: 16, alignItems: "start", marginTop: 8 }}>
        <Card
          title="Waiting for you"
          sub="Approvals and blocked work"
          action={
            <button className="btn btn-l btn-sm" onClick={() => go("appr")}>
              View all
            </button>
          }
        >
          {waitingRows.length === 0 ? (
            <div style={{ padding: 22, display: "flex", flexDirection: "column", alignItems: "center", gap: 12, textAlign: "center" }} className="sub">
              {loaded ? <Art src={ART.checklist} width={180} /> : null}
              {loaded ? "All clear. New requests land here the moment an agent pauses." : "Loading…"}
            </div>
          ) : (
            waitingRows.map((w) => (
              <div key={w.key} style={{ display: "flex", alignItems: "center", gap: 10, padding: "12px 18px", borderTop: "1px solid var(--bs)" }}>
                <Avatar name={w.name} />
                <div style={{ flex: 1, minWidth: 0, display: "flex", flexDirection: "column" }}>
                  <span style={{ fontSize: 14, fontWeight: 500 }}>{w.title}</span>
                  <span className="sub">{w.meta}</span>
                </div>
                <button className="btn btn-sm" onClick={w.open}>
                  {w.action}
                </button>
              </div>
            ))
          )}
        </Card>
        <Card
          title="In progress"
          sub="Assignments with live status"
          action={
            <button className="btn btn-l btn-sm" onClick={() => go("assign")}>
              View all
            </button>
          }
        >
          {inProgress.length === 0 ? (
            <div style={{ padding: 22, display: "flex", flexDirection: "column", alignItems: "center", gap: 12, textAlign: "center" }} className="sub">
              {assignments.at ? <Art src={ART.schedules} width={180} /> : null}
              {assignments.at ? "Nothing is running right now." : "Loading…"}
            </div>
          ) : (
            inProgress.map((a) => (
              <button
                key={a.id}
                onClick={() => go({ view: "assign", select: a.id })}
                style={{ display: "flex", alignItems: "center", gap: 10, padding: "12px 18px", border: 0, borderTop: "1px solid var(--bs)", background: "transparent", width: "100%", textAlign: "left", cursor: "pointer" }}
              >
                <Avatar name={a.agent} />
                <div style={{ flex: 1, minWidth: 0, display: "flex", flexDirection: "column", gap: 6 }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <span style={{ fontSize: 14, fontWeight: 500, flex: 1 }}>{a.title}</span>
                    <StatusPill status={a.status} />
                  </div>
                  {a.progress != null ? (
                    <div style={{ height: 6, borderRadius: 3, background: "var(--s3)", overflow: "hidden" }}>
                      <div style={{ height: 6, width: `${a.progress}%`, background: "var(--br)" }} />
                    </div>
                  ) : null}
                </div>
              </button>
            ))
          )}
        </Card>
        <Card
          title="This week"
          sub="Recent results"
          action={
            <button className="btn btn-l btn-sm" onClick={() => web("/home")}>
              Results ↗
            </button>
          }
        >
          <div style={{ display: "grid", gridTemplateColumns: "repeat(2, minmax(0, 1fr))", gap: 10, padding: "14px 18px" }}>
            <div className="tile good">
              <b>{totals.data.hoursSaved == null ? "–" : `${totals.data.hoursSaved} h`}</b>
              <span style={{ fontSize: 12 }}>Hours saved</span>
            </div>
            <div className="tile">
              <b>{totals.data.completed == null ? "–" : totals.data.completed}</b>
              <span className="sub">Tasks completed</span>
            </div>
          </div>
          {results.map((r) => (
            <div key={r.id} style={{ display: "flex", alignItems: "flex-start", gap: 10, padding: "10px 18px", borderTop: "1px solid var(--bs)" }}>
              <Icon name="checkc" style={{ color: "var(--ok)", marginTop: 2 }} />
              <div style={{ flex: 1, display: "flex", flexDirection: "column", minWidth: 0 }}>
                <span style={{ fontSize: 13, fontWeight: 500 }}>{r.title}</span>
                <span className="sub">{[r.agent, clock(r.finishedAt || r.createdAt)].filter(Boolean).join(" · ")}</span>
              </div>
            </div>
          ))}
        </Card>
      </div>
    </div>
  )
}
