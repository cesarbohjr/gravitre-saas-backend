"use client"

import { useEffect, useMemo, useRef, useState, type CSSProperties, type DragEvent } from "react"
import Link from "next/link"
import { APP_ROUTES } from "@/lib/app-routes"
import { relativeTime } from "@/lib/agent-job-result"
import {
  RANGE_LONG,
  REPORTS_PRESETS,
  REPORTS_RANGES,
  REPORTS_WIDGETS,
  moveWidget,
  nextSpan,
  seriesColor,
  type HomeReports,
  type ReportsPresetId,
  type ReportsRange,
  type ReportsWidget,
  type ReportsWidgetType,
} from "@/lib/dashboard/home-reports"
import type { Agent } from "@/types/api"
import { workforceState } from "@/components/home/operating-flow"

const KPI_ICONS: Partial<Record<ReportsWidgetType, string>> = {
  kpi_runs: "M7 4.5v15l12-7.5z",
  kpi_success: "M4 12.5l5 5 11-11",
  kpi_latency: "M12 7v5l3 2M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18z",
  kpi_saved: "M12 3v4M12 17v4M3 12h4M17 12h4M6 6l2.5 2.5M15.5 15.5 18 18M6 18l2.5-2.5M15.5 8.5 18 6",
  kpi_cost: "M12 3v18M17 7.5c0-1.9-2.2-3-5-3s-5 1.1-5 3 2 2.7 5 3.5 5 1.6 5 3.5-2.2 3-5 3-5-1.1-5-3",
  kpi_decisions: "M12 3 5 6v5c0 4.5 3 8 7 10 4-2 7-5.5 7-10V6zM9 12l2 2 4-4",
}

const MUTED: CSSProperties = { fontSize: 13, color: "var(--gv-muted)" }
const MONO = "gv-mono"

function clamp(x: number) {
  return x < 0 ? 0 : x > 1 ? 1 : x
}
function ease(x: number) {
  return 1 - Math.pow(1 - x, 3)
}
function fmt(n: number) {
  return Math.round(n).toLocaleString("en-US")
}
function fmtDuration(sec: number) {
  if (sec < 60) return `${sec.toFixed(1)}s`
  if (sec < 3600) return `${(sec / 60).toFixed(1)}m`
  return `${(sec / 3600).toFixed(1)}h`
}

/** 0→1 over 1.5s after each change of `playKey`, like the design's entrance; 1 at once with reduced motion. */
function useEntrance(playKey: string) {
  const [t, setT] = useState(0)
  useEffect(() => {
    if (typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches) {
      setT(1)
      return
    }
    let raf = 0
    let start: number | null = null
    setT(0)
    const step = (now: number) => {
      if (start === null) start = now
      const next = Math.min(1, (now - start) / 1500)
      setT(next)
      if (next < 1) raf = requestAnimationFrame(step)
    }
    raf = requestAnimationFrame(step)
    return () => cancelAnimationFrame(raf)
  }, [playKey])
  return t
}

function spark(values: number[], w: number, h: number, pad: number) {
  const vals = values.length > 1 ? values : [values[0] ?? 0, values[0] ?? 0]
  const mn = Math.min(...vals)
  const mx = Math.max(...vals)
  const rg = mx - mn || 1
  const pts = vals.map((v, i) => [(i / (vals.length - 1)) * w, pad + (1 - (v - mn) / rg) * (h - pad * 2)])
  const line = pts.map((p, i) => `${i ? "L" : "M"}${p[0].toFixed(1)} ${p[1].toFixed(1)}`).join(" ")
  return { line, area: `${line} L${w} ${h} L0 ${h} Z` }
}

function heatColor(v: number) {
  const stops = [[243, 251, 247], [205, 235, 220], [110, 214, 165], [25, 195, 125], [11, 138, 92]]
  const x = clamp(v) * 4
  const i = Math.min(3, Math.floor(x))
  const f = x - i
  const a = stops[i]
  const b = stops[i + 1]
  return `rgb(${[0, 1, 2].map((k) => Math.round(a[k] + (b[k] - a[k]) * f)).join(",")})`
}

function DeltaChip({ value, goodWhenUp = true, unit = "%" }: { value: number | null; goodWhenUp?: boolean; unit?: string }) {
  if (value === null || !Number.isFinite(value)) return null
  const good = goodWhenUp ? value >= 0 : value <= 0
  return (
    <span
      style={{
        fontSize: 13,
        fontWeight: 600,
        padding: "3px 8px",
        borderRadius: 999,
        background: good ? "var(--gv-mint)" : "var(--gv-amber-bg)",
        color: good ? "var(--gv-brand-strong)" : "var(--gv-amber-text)",
      }}
    >
      {value >= 0 ? "↑ " : "↓ "}
      {Math.abs(value).toFixed(1)}
      {unit}
    </span>
  )
}

type Ctx = { data: HomeReports | undefined; t: (idx: number, extra?: number) => number; range: ReportsRange; agents: Agent[] }

function EmptyNote({ art, text, href, cta }: { art: string; text: string; href?: string; cta?: string }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", textAlign: "center", gap: 10, margin: "auto 0", padding: "12px 0" }}>
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src={`/illustrations/${art}.svg`} alt="" width={150} height={112} style={{ borderRadius: 12, width: 150, height: "auto" }} />
      <div style={{ fontSize: 14, color: "var(--gv-muted)", maxWidth: 300 }}>{text}</div>
      {href && cta ? (
        <Link href={href} style={{ fontSize: 14, fontWeight: 500, textDecoration: "none" }}>
          {cta} →
        </Link>
      ) : null}
    </div>
  )
}

function KpiBody({ type, ctx, idx }: { type: ReportsWidgetType; ctx: Ctx; idx: number }) {
  const d = ctx.data
  const e = ease(ctx.t(idx))
  const totals = d?.totals
  const buckets = d?.buckets ?? []
  let display = "—"
  let delta: number | null = null
  let goodWhenUp = true
  let unit = "%"
  let foot = ""
  let series: number[] = buckets.map((b) => b.total)
  const agentCount = d?.series.filter((s) => s.agentId).length ?? 0
  if (type === "kpi_runs") {
    display = totals ? fmt(totals.runs * e) : "—"
    delta = d?.deltas.runs ?? null
    foot = `across ${agentCount} agent${agentCount === 1 ? "" : "s"}`
  } else if (type === "kpi_success") {
    display = totals?.successRate != null ? `${(totals.successRate * e).toFixed(1)}%` : "—"
    delta = d?.deltas.successRate ?? null
    unit = " pts"
    foot = "completed, not failed"
    let last = 0
    series = buckets.map((b) => (b.successRate == null ? last : (last = b.successRate)))
  } else if (type === "kpi_latency") {
    display = totals?.medianDurationSec != null ? fmtDuration(totals.medianDurationSec * e) : "—"
    delta = d?.deltas.medianDurationSec ?? null
    goodWhenUp = false
    foot = "median per task"
    let last = 0
    series = buckets.map((b) => (b.medianDurationSec == null ? last : (last = b.medianDurationSec)))
  } else if (type === "kpi_saved") {
    display = totals ? `${fmt(totals.hoursSaved * e)}h` : "—"
    delta = d?.deltas.hoursSaved ?? null
    foot = "at ~4 min per task"
    series = buckets.map((b) => b.completed)
  } else if (type === "kpi_cost") {
    display = totals ? `$${(totals.modelSpendUsd * e).toFixed(2)}` : "—"
    delta = d?.deltas.modelSpendUsd ?? null
    goodWhenUp = false
    foot = `tokens across ${totals?.modelCount ?? 0} model${totals?.modelCount === 1 ? "" : "s"}`
  } else if (type === "kpi_decisions") {
    display = totals ? fmt(totals.decisionsResolved * e) : "—"
    delta = d?.deltas.decisionsResolved ?? null
    foot = "approvals cleared"
  }
  const sp = spark(series.length ? series : [0], 120, 36, 3)
  return (
    <>
      <div style={{ display: "flex", alignItems: "baseline", gap: 10, flexWrap: "wrap" }}>
        <div style={{ fontSize: 36, fontWeight: 700, letterSpacing: "-0.03em", fontVariantNumeric: "tabular-nums" }}>{display}</div>
        <DeltaChip value={delta} goodWhenUp={goodWhenUp} unit={unit} />
      </div>
      <div style={{ ...MUTED, marginTop: 4 }}>{foot} · vs prior period</div>
      <svg viewBox="0 0 120 36" preserveAspectRatio="none" width="100%" height={48} style={{ display: "block", marginTop: "auto", paddingTop: 12, overflow: "visible" }} aria-hidden>
        <path d={sp.area} fill="#19C37D" opacity={(0.12 * e).toFixed(3)} />
        <path d={sp.line} fill="none" stroke="#19C37D" strokeWidth={2} vectorEffect="non-scaling-stroke" strokeLinecap="round" strokeLinejoin="round" pathLength={100} strokeDasharray={100} strokeDashoffset={(100 - 100 * e).toFixed(2)} />
      </svg>
    </>
  )
}

function VolumeBody({ ctx, idx }: { ctx: Ctx; idx: number }) {
  const d = ctx.data
  const buckets = d?.buckets ?? []
  const series = d?.series ?? []
  if (d && d.totals.runs === 0) {
    return <EmptyNote art="spot-reports" text="No runs in this range yet. A test run fills every chart here." href={APP_ROUTES.workflows} cta="Run a workflow" />
  }
  const mx = Math.max(1, ...buckets.map((b) => b.total))
  const stepv = Math.pow(10, Math.floor(Math.log10(Math.max(mx / 4, 1))))
  const nice = Math.max(1, Math.ceil(mx / 4 / stepv) * stepv)
  const ymax = nice * 4
  const n = buckets.length || 7
  const gap = n > 20 ? "3px" : n > 10 ? "6px" : "12px"
  return (
    <>
      <div style={{ display: "flex", gap: 16, flexWrap: "wrap", fontSize: 13, color: "var(--gv-muted)", marginBottom: 12 }}>
        {series.map((s) => (
          <span key={s.key} style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
            <span style={{ width: 10, height: 10, borderRadius: 3, background: seriesColor(series, s.key) }} />
            {s.name}
          </span>
        ))}
      </div>
      <div style={{ position: "relative", height: 220, paddingLeft: 36, marginTop: "auto" }}>
        {[0, 1, 2, 3, 4].map((q) => (
          <div key={q} style={{ position: "absolute", left: 36, right: 0, bottom: `${q * 25}%`, borderTop: "1px dashed var(--gv-subtle)" }}>
            <span className={MONO} style={{ position: "absolute", left: -36, top: -8, fontSize: 11, color: "var(--gv-faint)" }}>{fmt(nice * q)}</span>
          </div>
        ))}
        <div style={{ position: "relative", display: "flex", alignItems: "flex-end", gap, height: "100%" }}>
          {buckets.map((b, bi) => {
            const be = ease(ctx.t(idx, (bi / n) * 0.45))
            const stack = series.filter((s) => b.bySeries[s.key])
            return (
              <div key={b.start} className="gv-col">
                {stack.map((s, si) => (
                  <div
                    key={s.key}
                    className="gv-seg-bar"
                    style={{
                      height: `${(((b.bySeries[s.key] ?? 0) / ymax) * 100 * be).toFixed(2)}%`,
                      background: seriesColor(series, s.key),
                      borderRadius: si === 0 && stack.length === 1 ? "3px" : si === 0 ? "0 0 3px 3px" : si === stack.length - 1 ? "3px 3px 0 0" : undefined,
                    }}
                  />
                ))}
                <div className="gv-tip">
                  {b.label} · {fmt(b.total)} runs
                </div>
              </div>
            )
          })}
        </div>
      </div>
      <div style={{ display: "flex", gap, paddingLeft: 36, marginTop: 8 }}>
        {buckets.map((b) => (
          <div key={b.start} className={MONO} style={{ flex: "1 1 0", minWidth: 0, textAlign: "center", fontSize: 11, color: "var(--gv-faint)", whiteSpace: "nowrap", overflow: "visible" }}>
            {b.axis}
          </div>
        ))}
      </div>
    </>
  )
}

function SuccessBody({ ctx, idx }: { ctx: Ctx; idx: number }) {
  const d = ctx.data
  const e = ease(ctx.t(idx))
  const pts = (d?.buckets ?? []).map((b, i, all) => ({ i, n: all.length, v: b.successRate })).filter((p) => p.v != null) as Array<{ i: number; n: number; v: number }>
  if (d && pts.length === 0) {
    return <EmptyNote art="moment-focus-time" text="No finished runs in this range yet, so there is no success rate to chart." />
  }
  const lo = Math.min(85, ...pts.map((p) => Math.floor(p.v / 5) * 5))
  const hi = 100
  const xy = pts.map((p) => [(p.n > 1 ? p.i / (p.n - 1) : 1) * 600, 200 - ((p.v - lo) / (hi - lo)) * 200])
  const line = xy.map((p, i) => `${i ? "L" : "M"}${p[0].toFixed(1)} ${p[1].toFixed(1)}`).join(" ")
  const last = xy[xy.length - 1] ?? [600, 200]
  const ticks = [lo, lo + (hi - lo) / 3, lo + (2 * (hi - lo)) / 3, hi].map((v) => Math.round(v))
  return (
    <>
      <div style={{ display: "flex", alignItems: "baseline", gap: 10, marginBottom: 10 }}>
        <span style={{ fontSize: 28, fontWeight: 700, letterSpacing: "-0.02em", fontVariantNumeric: "tabular-nums" }}>
          {d?.totals.successRate != null ? `${(d.totals.successRate * e).toFixed(1)}%` : "—"}
        </span>
        <span style={{ fontSize: 13, color: "var(--gv-muted)" }}>average · target 95%</span>
      </div>
      <div style={{ position: "relative", height: 200, marginTop: "auto", paddingLeft: 36 }}>
        {ticks.map((v) => (
          <div key={v} style={{ position: "absolute", left: 36, right: 0, bottom: `${((v - lo) / (hi - lo)) * 100}%`, borderTop: "1px dashed var(--gv-subtle)" }}>
            <span className={MONO} style={{ position: "absolute", left: -36, top: -8, fontSize: 11, color: "var(--gv-faint)" }}>{v}%</span>
          </div>
        ))}
        <div style={{ position: "absolute", left: 36, right: 0, bottom: `${((95 - lo) / (hi - lo)) * 100}%`, borderTop: "1.5px solid #E2A33A" }}>
          <span style={{ position: "absolute", right: 0, top: -20, fontSize: 11, fontWeight: 600, color: "var(--gv-amber-text)" }}>Target</span>
        </div>
        <svg viewBox="0 0 600 200" preserveAspectRatio="none" style={{ position: "absolute", left: 36, top: 0, width: "calc(100% - 36px)", height: "100%", overflow: "visible" }} aria-hidden>
          <defs>
            <linearGradient id="gvSuccFill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#19C37D" stopOpacity="0.28" />
              <stop offset="100%" stopColor="#19C37D" stopOpacity="0" />
            </linearGradient>
          </defs>
          {xy.length > 1 ? <path d={`${line} L${last[0]} 200 L${xy[0][0]} 200 Z`} fill="url(#gvSuccFill)" opacity={e.toFixed(3)} /> : null}
          <path d={line} fill="none" stroke="#0B8A5C" strokeWidth={2.5} vectorEffect="non-scaling-stroke" strokeLinecap="round" strokeLinejoin="round" pathLength={100} strokeDasharray={100} strokeDashoffset={(100 - 100 * e).toFixed(2)} />
        </svg>
        <span style={{ position: "absolute", left: `calc(36px + (100% - 36px) * ${(last[0] / 600).toFixed(3)})`, top: `${((last[1] / 200) * 100).toFixed(2)}%`, width: 12, height: 12, margin: "-6px 0 0 -6px", borderRadius: "50%", background: "var(--gv-card)", border: "3px solid #0B8A5C", opacity: e }} />
      </div>
    </>
  )
}

function DonutBody({ ctx, idx }: { ctx: Ctx; idx: number }) {
  const d = ctx.data
  const e = ease(ctx.t(idx))
  const series = d?.series ?? []
  const tot = d?.totals.runs ?? 0
  const C = 2 * Math.PI * 70
  let cum = 0
  const slices = series.map((s) => {
    const fr = tot ? s.runs / tot : 0
    const len = Math.max(0, fr * C * e - 3)
    const slice = { key: s.key, color: seriesColor(series, s.key), name: s.name, pct: `${Math.round(fr * 100)}%`, dash: `${len.toFixed(1)} ${C.toFixed(1)}`, offset: (-cum * C * e).toFixed(1) }
    cum += fr
    return slice
  })
  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 16, marginTop: "auto" }}>
      <div style={{ position: "relative", width: 180, height: 180 }}>
        <svg viewBox="0 0 180 180" width={180} height={180} style={{ transform: "rotate(-90deg)" }} aria-hidden>
          <circle cx="90" cy="90" r="70" fill="none" stroke="var(--gv-subtle)" strokeWidth={20} />
          {slices.map((s) => (
            <circle key={s.key} cx="90" cy="90" r="70" fill="none" stroke={s.color} strokeWidth={20} strokeDasharray={s.dash} strokeDashoffset={s.offset} />
          ))}
        </svg>
        <div style={{ position: "absolute", inset: 0, display: "grid", placeItems: "center", textAlign: "center" }}>
          <div>
            <div style={{ fontSize: 30, fontWeight: 700, letterSpacing: "-0.02em", fontVariantNumeric: "tabular-nums" }}>{fmt(tot * e)}</div>
            <div style={{ fontSize: 12, color: "var(--gv-muted)" }}>runs</div>
          </div>
        </div>
      </div>
      <div style={{ width: "100%", display: "grid", gap: 8 }}>
        {slices.length === 0 ? <div style={{ ...MUTED, textAlign: "center" }}>No runs in this range yet.</div> : null}
        {slices.map((s) => (
          <div key={s.key} style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 13 }}>
            <span style={{ width: 10, height: 10, borderRadius: 3, background: s.color }} />
            <span style={{ flex: 1 }}>{s.name}</span>
            <strong style={{ fontVariantNumeric: "tabular-nums" }}>{s.pct}</strong>
          </div>
        ))}
      </div>
    </div>
  )
}

function GaugeBody({ ctx, idx }: { ctx: Ctx; idx: number }) {
  const u = ctx.data?.utilization
  const e = ease(ctx.t(idx))
  const pct = u?.percent ?? 0
  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", marginTop: "auto" }}>
      <div style={{ position: "relative", width: "100%", maxWidth: 220 }}>
        <svg viewBox="0 0 180 104" width="100%" aria-hidden>
          <path d="M14 94 A76 76 0 0 1 166 94" fill="none" stroke="var(--gv-subtle)" strokeWidth={16} strokeLinecap="round" />
          <path d="M14 94 A76 76 0 0 1 166 94" fill="none" stroke="#19C37D" strokeWidth={16} strokeLinecap="round" pathLength={100} strokeDasharray={100} strokeDashoffset={(100 - pct * e).toFixed(2)} />
        </svg>
        <div style={{ position: "absolute", left: 0, right: 0, bottom: 4, textAlign: "center" }}>
          <div style={{ fontSize: 32, fontWeight: 700, letterSpacing: "-0.02em", fontVariantNumeric: "tabular-nums" }}>
            {u?.percent != null ? `${Math.round(pct * e)}%` : "—"}
          </div>
        </div>
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10, width: "100%", marginTop: 18 }}>
        <div style={{ background: "var(--gv-hover)", borderRadius: 10, padding: "10px 12px" }}>
          <div style={{ fontSize: 12, color: "var(--gv-muted)" }}>Executing</div>
          <div style={{ fontWeight: 600, fontVariantNumeric: "tabular-nums" }}>{u ? `${fmt(u.executingHours * e)} h` : "—"}</div>
        </div>
        <div style={{ background: "var(--gv-hover)", borderRadius: 10, padding: "10px 12px" }}>
          <div style={{ fontSize: 12, color: "var(--gv-muted)" }}>Idle</div>
          <div style={{ fontWeight: 600, fontVariantNumeric: "tabular-nums" }}>{u?.idleHours != null ? `${fmt(u.idleHours * e)} h` : "—"}</div>
        </div>
      </div>
    </div>
  )
}

function HeatBody({ ctx, idx }: { ctx: Ctx; idx: number }) {
  const rows = ctx.data?.heat ?? ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"].map((day) => ({ day, cells: Array(12).fill(0) as number[] }))
  const max = Math.max(1, ...rows.flatMap((r) => r.cells))
  return (
    <div style={{ display: "grid", gap: 4, marginTop: "auto" }}>
      {rows.map((row, ri) => (
        <div key={row.day} style={{ display: "grid", gridTemplateColumns: "36px repeat(12, minmax(0, 1fr))", gap: 4, alignItems: "center" }}>
          <span className={MONO} style={{ fontSize: 11, color: "var(--gv-faint)" }}>{row.day}</span>
          {row.cells.map((v, ci) => (
            <div
              key={ci}
              className="gv-heat"
              title={`${row.day} ${ci * 2}:00 · ${fmt(v)} run${v === 1 ? "" : "s"}`}
              style={{ height: 22, background: heatColor(v / max), opacity: clamp(ctx.t(idx, ((ri * 12 + ci) / 84) * 0.7) * 1.2).toFixed(3) }}
            />
          ))}
        </div>
      ))}
      <div className={MONO} style={{ display: "grid", gridTemplateColumns: "36px repeat(6, minmax(0, 1fr))", gap: 4, marginTop: 4, fontSize: 11, color: "var(--gv-faint)" }}>
        <span />
        <span>12a</span>
        <span>4a</span>
        <span>8a</span>
        <span>12p</span>
        <span>4p</span>
        <span>8p</span>
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: 8, justifyContent: "flex-end", fontSize: 12, color: "var(--gv-muted)", marginTop: 6 }}>
        Fewer
        <span style={{ display: "flex", gap: 3 }}>
          {["#DDF3E8", "#CDEBDC", "#6ED6A5", "#19C37D", "#0A6B47"].map((c) => (
            <span key={c} style={{ width: 14, height: 10, borderRadius: 2, background: c }} />
          ))}
        </span>
        More
      </div>
    </div>
  )
}

function FunnelBody({ ctx, idx }: { ctx: Ctx; idx: number }) {
  const stages = ctx.data?.funnel ?? []
  const top = stages[0]?.value ?? 0
  const cols = ["#0A6B47", "#19C37D", "#19C37D", "#2B59E0"]
  if (ctx.data && stages.every((s) => s.value === 0)) {
    return <EmptyNote art="dept-sales" text="No lead activity recorded yet. Connect your CRM and turn on the Growth plays to fill this pipeline." href={APP_ROUTES.plays} cta="Open plays" />
  }
  return (
    <div style={{ display: "grid", gap: 12, marginTop: "auto" }}>
      {stages.map((st, si) => {
        const se = ease(ctx.t(idx, si * 0.12))
        const prev = si ? stages[si - 1].value : 0
        return (
          <div key={st.key}>
            <div style={{ display: "flex", justifyContent: "space-between", fontSize: 13, marginBottom: 6 }}>
              <span style={{ fontWeight: 500 }}>{st.name}</span>
              <span style={{ color: "var(--gv-muted)", fontVariantNumeric: "tabular-nums" }}>
                <strong style={{ color: "var(--gv-text)" }}>{fmt(st.value * se)}</strong> · {si ? (prev ? `${Math.round((st.value / prev) * 100)}% of prev` : "—") : "100%"}
              </span>
            </div>
            <div style={{ height: 14, background: "var(--gv-subtle)", borderRadius: 7, overflow: "hidden" }}>
              <div style={{ height: "100%", width: `${top ? ((st.value / top) * 100 * se).toFixed(1) : 0}%`, background: cols[si] ?? "#19C37D", borderRadius: 7 }} />
            </div>
          </div>
        )
      })}
    </div>
  )
}

function MonitorBody({ ctx, idx }: { ctx: Ctx; idx: number }) {
  const d = ctx.data
  const e = ease(ctx.t(idx))
  const series = d?.series ?? []
  const byId = new Map(ctx.agents.map((a) => [a.id, a]))
  const rows = [
    ...series,
    // Agents with no runs in range still belong in a monitor of live agents.
    ...ctx.agents
      .filter((a) => !series.some((s) => s.agentId === a.id))
      .map((a) => ({ key: a.id, agentId: a.id, name: a.name, model: a.model ?? null, runs: 0, completed: 0, failed: 0, successRate: null, latencyP50Sec: null, lastRunAt: null, spark: Array(12).fill(0) as number[] })),
  ]
  if (d && rows.length === 0) {
    return <EmptyNote art="spot-agents" text="No agents yet. Hire one and its runs show up here." href={`${APP_ROUTES.agents}/new`} cta="Hire an agent" />
  }
  return (
    <div style={{ overflowX: "auto", margin: "0 -20px -20px" }}>
      <table className="gv-table">
        <thead>
          <tr style={{ textAlign: "left", color: "var(--gv-muted)", fontSize: 12 }}>
            <th style={{ padding: "10px 20px", fontWeight: 500 }}>Agent</th>
            <th style={{ padding: 10, fontWeight: 500 }}>Model</th>
            <th style={{ padding: 10, fontWeight: 500 }}>Status</th>
            <th style={{ padding: 10, fontWeight: 500, textAlign: "right" }}>Runs</th>
            <th style={{ padding: 10, fontWeight: 500, textAlign: "right" }}>Success</th>
            <th style={{ padding: 10, fontWeight: 500 }}>Latency p50</th>
            <th style={{ padding: "10px 20px", fontWeight: 500 }}>Last run</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((m) => {
            const agent = m.agentId ? byId.get(m.agentId) : undefined
            const state = agent ? workforceState(agent.status) : "available"
            const status =
              state === "executing" ? { label: "Executing", bg: "var(--gv-mint)", fg: "var(--gv-brand-strong)", dot: "#19C37D", ping: true }
              : state === "attention" ? { label: "Needs attention", bg: "var(--gv-red-bg)", fg: "var(--gv-red)", dot: "#C2412D", ping: false }
              : state === "paused" ? { label: "Paused", bg: "var(--gv-subtle)", fg: "var(--gv-muted)", dot: "#8A8B85", ping: false }
              : { label: "Active", bg: "var(--gv-mint)", fg: "var(--gv-brand-strong)", dot: "#19C37D", ping: true }
            const color = seriesColor(series, m.key)
            const peak = Math.max(1, ...m.spark)
            const model = m.model ?? agent?.model ?? null
            return (
              <tr key={m.key}>
                <td style={{ padding: "14px 20px", fontWeight: 600 }}>
                  <span style={{ display: "inline-flex", alignItems: "center", gap: 10 }}>
                    <span style={{ width: 10, height: 10, borderRadius: 3, background: color }} />
                    {m.agentId ? (
                      <Link href={`${APP_ROUTES.agents}/${m.agentId}`} style={{ color: "inherit", textDecoration: "none" }}>{m.name}</Link>
                    ) : (
                      <Link href={APP_ROUTES.workflows} style={{ color: "inherit", textDecoration: "none" }}>{m.name}</Link>
                    )}
                  </span>
                </td>
                <td className={MONO} style={{ padding: "14px 10px", fontSize: 13, color: "var(--gv-muted)" }}>{model && model !== "auto" ? model : m.agentId ? "auto" : "—"}</td>
                <td style={{ padding: "14px 10px" }}>
                  <span style={{ display: "inline-flex", alignItems: "center", gap: 8, background: status.bg, color: status.fg, fontSize: 13, fontWeight: 500, padding: "4px 10px", borderRadius: 999 }}>
                    <span className={status.ping ? "gv-ping" : undefined} style={{ width: 8, height: 8, borderRadius: "50%", display: "inline-block", background: status.dot }} />
                    {status.label}
                  </span>
                </td>
                <td style={{ padding: "14px 10px", textAlign: "right", fontVariantNumeric: "tabular-nums" }}>{fmt(m.runs * e)}</td>
                <td style={{ padding: "14px 10px", textAlign: "right", fontVariantNumeric: "tabular-nums" }}>{m.successRate != null ? `${m.successRate.toFixed(1)}%` : "—"}</td>
                <td style={{ padding: "14px 10px" }}>
                  <span style={{ display: "inline-flex", alignItems: "flex-end", gap: 10 }}>
                    <span style={{ display: "inline-flex", alignItems: "flex-end", gap: 2, height: 22 }}>
                      {m.spark.map((v, si) => (
                        <span key={si} style={{ width: 4, height: `${Math.max(8, (v / peak) * 100 * e).toFixed(0)}%`, background: si === m.spark.length - 1 ? color : "var(--gv-mint-2)", borderRadius: 1 }} />
                      ))}
                    </span>
                    <span className={MONO} style={{ fontSize: 13 }}>{m.latencyP50Sec != null ? fmtDuration(m.latencyP50Sec) : "—"}</span>
                  </span>
                </td>
                <td className={MONO} style={{ padding: "14px 20px", color: "var(--gv-muted)", fontSize: 13 }}>{m.lastRunAt ? relativeTime(m.lastRunAt) : "No runs yet"}</td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

function widgetSub(type: ReportsWidgetType, range: ReportsRange) {
  const long = RANGE_LONG[range]
  if (type === "volume") return `${long} · stacked by agent`
  if (type === "success") return `${long} · completed vs failed runs`
  if (type === "donut") return long
  if (type === "gauge") return "Share of agent hours spent executing"
  if (type === "heat") return "Runs by weekday and 2 hour block"
  if (type === "funnel") return "Marketing Agent to Sales Agent handoff"
  if (type === "monitor") return "Live agents · model, status, latency, last run"
  return ""
}

export function ReportsControls({
  range,
  setRange,
  preset,
  setPreset,
  editing,
  setEditing,
  openLibrary,
  reset,
}: {
  range: ReportsRange
  setRange: (r: ReportsRange) => void
  preset: ReportsPresetId
  setPreset: (p: ReportsPresetId) => void
  editing: boolean
  setEditing: (v: boolean) => void
  openLibrary: () => void
  reset: () => void
}) {
  return (
    <div style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
      <div role="group" aria-label="Date range" style={{ display: "flex", background: "var(--gv-card)", border: "1px solid var(--gv-border)", borderRadius: 10, padding: 3 }}>
        {REPORTS_RANGES.map((r) => (
          <button key={r} type="button" className={`gv-rng${range === r ? " on" : ""}`} aria-pressed={range === r} onClick={() => setRange(r)}>
            {r}
          </button>
        ))}
      </div>
      <label style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 14, color: "var(--gv-muted)" }}>
        View
        <select className="gv-select" value={preset} onChange={(e) => setPreset(e.target.value as ReportsPresetId)}>
          {(Object.keys(REPORTS_PRESETS) as ReportsPresetId[]).map((p) => (
            <option key={p} value={p}>
              {REPORTS_PRESETS[p].name}
            </option>
          ))}
        </select>
      </label>
      <button type="button" className="gv-btn line" onClick={openLibrary}>
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.2} strokeLinecap="round" aria-hidden>
          <path d="M12 5v14M5 12h14" />
        </svg>
        Add KPI
      </button>
      {editing ? (
        <button type="button" className="gv-btn text" onClick={reset}>
          Reset layout
        </button>
      ) : null}
      <button type="button" className={editing ? "gv-btn dark tall" : "gv-btn line"} onClick={() => setEditing(!editing)}>
        {editing ? "Done" : "Customize"}
      </button>
    </div>
  )
}

export function ReportsView({
  data,
  error,
  range,
  preset,
  widgets,
  setWidgets,
  editing,
  showLibrary,
  closeLibrary,
  agents,
}: {
  data: HomeReports | undefined
  error: unknown
  range: ReportsRange
  preset: ReportsPresetId
  widgets: ReportsWidget[]
  setWidgets: (list: ReportsWidget[]) => void
  editing: boolean
  showLibrary: boolean
  closeLibrary: () => void
  agents: Agent[]
}) {
  const [dragId, setDragId] = useState<string | null>(null)
  const [overId, setOverId] = useState<string | null>(null)
  const uid = useRef(0)
  const playKey = `${range}:${preset}:${data ? "1" : "0"}:${widgets.length}`
  const T = useEntrance(playKey)
  const ctx: Ctx = useMemo(
    () => ({ data, range, agents, t: (idx: number, extra = 0) => clamp(T * 1.6 - idx * 0.05 - extra) }),
    [data, range, agents, T],
  )
  const presetName = REPORTS_PRESETS[preset].name
  const used = new Set(widgets.map((w) => w.type))
  const library = (Object.keys(REPORTS_WIDGETS) as ReportsWidgetType[]).filter((t) => !used.has(t))

  return (
    <div data-dashboard-view="reports">
      <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap", padding: "16px 0 20px", fontSize: 14, color: "var(--gv-muted)" }}>
        {editing ? (
          <span style={{ display: "inline-flex", alignItems: "center", gap: 8, color: "var(--gv-brand-strong)", fontWeight: 500 }}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor" aria-hidden>
              {[6, 12, 18].flatMap((cy) => [9, 15].map((cx) => <circle key={`${cx}-${cy}`} cx={cx} cy={cy} r={1.6} />))}
            </svg>
            Drag widgets to reorder. Use the size button to cycle widths. Your layout is saved for {presetName}.
          </span>
        ) : (
          <span style={{ display: "inline-flex", alignItems: "center", gap: 8 }}>
            <span className="gv-ping" style={{ background: error ? "#E2A33A" : "#19C37D", width: 8, height: 8 }} />
            {presetName} view · {RANGE_LONG[range]} ·{" "}
            {error ? "could not refresh, showing the last data loaded" : data ? `updated ${relativeTime(data.generatedAt)}` : "loading"}
          </span>
        )}
        <span className={MONO} style={{ marginLeft: "auto", fontSize: 12, border: "1px solid var(--gv-border)", borderRadius: 999, padding: "4px 10px", background: "var(--gv-card)" }}>
          Live data
        </span>
      </div>

      {showLibrary ? (
        <section className="gv-w" style={{ marginBottom: 20, background: "var(--gv-brand-surface)", borderColor: "var(--gv-mint-2)" }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12, marginBottom: 14 }}>
            <div>
              <div style={{ fontWeight: 600, fontSize: 16 }}>KPI library</div>
              <div style={{ fontSize: 14, color: "var(--gv-muted)" }}>Click a widget to add it to the end of your layout, then drag it into place.</div>
            </div>
            <button type="button" className="gv-ctl" aria-label="Close library" onClick={closeLibrary}>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" aria-hidden>
                <path d="M6 6l12 12M18 6 6 18" />
              </svg>
            </button>
          </div>
          {library.length === 0 ? <div style={{ fontSize: 14, color: "var(--gv-muted)" }}>Every widget is already on your dashboard.</div> : null}
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(220px, 1fr))", gap: 10 }}>
            {library.map((t) => (
              <button
                key={t}
                type="button"
                className="gv-lib"
                onClick={() => {
                  uid.current += 1
                  setWidgets([...widgets, { id: `${t}-${Date.now().toString(36)}${uid.current}`, type: t, span: REPORTS_WIDGETS[t].span }])
                }}
              >
                <span style={{ width: 36, height: 36, borderRadius: 10, background: "var(--gv-mint)", display: "grid", placeItems: "center", flex: "0 0 auto" }}>
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#0B8A5C" strokeWidth={2} strokeLinecap="round" aria-hidden>
                    <path d="M12 5v14M5 12h14" />
                  </svg>
                </span>
                <span>
                  <span style={{ display: "block", fontWeight: 600, fontSize: 14 }}>{REPORTS_WIDGETS[t].title}</span>
                  <span className={MONO} style={{ display: "block", fontSize: 12, color: "var(--gv-muted)" }}>
                    {REPORTS_WIDGETS[t].kind} · {REPORTS_WIDGETS[t].span}x1
                  </span>
                </span>
              </button>
            ))}
          </div>
        </section>
      ) : null}

      {widgets.length === 0 ? (
        <div className="gv-w" style={{ alignItems: "center", textAlign: "center" }}>
          <EmptyNote art="spot-reports" text="Your board is empty. Add a KPI to start your master view." />
        </div>
      ) : null}

      <div className="gv-grid">
        {widgets.map((w, idx) => {
          const meta = REPORTS_WIDGETS[w.type]
          const isKpi = w.type.startsWith("kpi_")
          const cls = ["gv-w", w.span === 1 ? "k1" : "", editing ? "edit" : "", overId === w.id && dragId !== w.id ? "over" : "", dragId === w.id ? "dragging" : ""].filter(Boolean).join(" ")
          const sub = widgetSub(w.type, range)
          return (
            <section
              key={w.id}
              className={cls}
              style={{ gridColumn: `span ${w.span}`, animationDelay: `${idx * 50}ms` }}
              draggable={editing}
              aria-label={meta.title}
              onDragStart={(ev: DragEvent) => {
                if (!editing) return
                try {
                  ev.dataTransfer.effectAllowed = "move"
                  ev.dataTransfer.setData("text/plain", w.id)
                } catch {
                  // some browsers block dataTransfer in synthetic drags
                }
                setDragId(w.id)
              }}
              onDragOver={(ev) => {
                if (!dragId) return
                ev.preventDefault()
                if (overId !== w.id) setOverId(w.id)
              }}
              onDrop={(ev) => {
                ev.preventDefault()
                if (dragId && dragId !== w.id) setWidgets(moveWidget(widgets, dragId, w.id))
                setDragId(null)
                setOverId(null)
              }}
              onDragEnd={() => {
                setDragId(null)
                setOverId(null)
              }}
            >
              <div style={{ display: "flex", alignItems: "flex-start", gap: 10, marginBottom: 14 }}>
                {isKpi ? (
                  <span style={{ width: 36, height: 36, borderRadius: 10, background: "var(--gv-mint)", display: "grid", placeItems: "center", flex: "0 0 auto" }}>
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#0B8A5C" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" aria-hidden>
                      <path d={KPI_ICONS[w.type]} />
                    </svg>
                  </span>
                ) : null}
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontWeight: 600, fontSize: isKpi ? 14 : 18, letterSpacing: "-0.01em" }}>{meta.title}</div>
                  {sub ? <div style={{ fontSize: 13, color: "var(--gv-muted)", marginTop: 2 }}>{sub}</div> : null}
                </div>
                {editing ? (
                  <div style={{ display: "flex", gap: 6, flex: "0 0 auto" }}>
                    <span className="gv-ctl" aria-hidden style={{ cursor: "grab" }}>
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
                        {[6, 12, 18].flatMap((cy) => [9, 15].map((cx) => <circle key={`${cx}-${cy}`} cx={cx} cy={cy} r={1.8} />))}
                      </svg>
                    </span>
                    <button
                      type="button"
                      className="gv-ctl"
                      style={{ width: "auto", padding: "0 8px" }}
                      aria-label={`Change ${meta.title} width`}
                      onClick={() => setWidgets(widgets.map((x) => (x.id === w.id ? { ...x, span: nextSpan(x.span) } : x)))}
                    >
                      {w.span}x1
                    </button>
                    {idx > 0 ? (
                      <button type="button" className="gv-ctl" aria-label={`Move ${meta.title} earlier`} onClick={() => setWidgets(moveWidget(widgets, w.id, widgets[idx - 1].id))}>
                        ↑
                      </button>
                    ) : null}
                    <button type="button" className="gv-ctl" aria-label={`Remove ${meta.title}`} onClick={() => setWidgets(widgets.filter((x) => x.id !== w.id))}>
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.2} strokeLinecap="round" aria-hidden>
                        <path d="M6 6l12 12M18 6 6 18" />
                      </svg>
                    </button>
                  </div>
                ) : null}
              </div>
              {!data && !error ? (
                <div style={{ display: "grid", gap: 10, marginTop: "auto" }}>
                  <div className="gv-skel" style={{ width: "70%" }} />
                  <div className="gv-skel" style={{ width: "92%" }} />
                  <div className="gv-skel" style={{ width: "54%" }} />
                </div>
              ) : isKpi ? (
                <KpiBody type={w.type} ctx={ctx} idx={idx} />
              ) : w.type === "volume" ? (
                <VolumeBody ctx={ctx} idx={idx} />
              ) : w.type === "success" ? (
                <SuccessBody ctx={ctx} idx={idx} />
              ) : w.type === "donut" ? (
                <DonutBody ctx={ctx} idx={idx} />
              ) : w.type === "gauge" ? (
                <GaugeBody ctx={ctx} idx={idx} />
              ) : w.type === "heat" ? (
                <HeatBody ctx={ctx} idx={idx} />
              ) : w.type === "funnel" ? (
                <FunnelBody ctx={ctx} idx={idx} />
              ) : (
                <MonitorBody ctx={ctx} idx={idx} />
              )}
            </section>
          )
        })}
      </div>
    </div>
  )
}
