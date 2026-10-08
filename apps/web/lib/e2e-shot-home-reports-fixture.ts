/**
 * Capture-only Reports payload for the /e2e/shots harness (never served in production).
 * Deterministic, shaped exactly like GET /api/metrics/home-reports.
 */
import type { HomeReports } from "@/lib/dashboard/home-reports"

const DOW = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]

function rng(seed: number) {
  let s = seed
  return () => {
    s = (s * 16807) % 2147483647
    return (s - 1) / 2147483646
  }
}

export function homeReportsShotFixture(): HomeReports {
  const r = rng(11)
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  const agents = [
    { key: "agt_lead_triage", name: "Inbound Lead Triage", model: "gpt-4o", lat: 3.1 },
    { key: "agt_deal_desk", name: "Deal Desk Sync", model: "gpt-4o", lat: 4.6 },
    { key: "agt_campaign_planner", name: "Campaign Planner", model: "gpt-4o-mini", lat: 5.8 },
  ]
  const buckets = Array.from({ length: 7 }, (_, i) => {
    const d = new Date(today.getTime() - (6 - i) * 86400000)
    const wk = d.getDay() === 0 || d.getDay() === 6 ? 0.45 : 1
    const tr = 0.75 + 0.5 * (i / 6)
    const a = Math.round((18 + r() * 16) * wk * tr)
    const b = Math.round((10 + r() * 12) * wk * tr)
    const c = Math.round((6 + r() * 10) * wk * tr)
    const total = a + b + c
    const sr = 93 + r() * 5.5
    const failed = Math.round(total * (1 - sr / 100))
    return {
      start: d.toISOString(),
      label: DOW[d.getDay()],
      axis: DOW[d.getDay()],
      bySeries: { agt_lead_triage: a, agt_deal_desk: b, agt_campaign_planner: c },
      total,
      completed: total - failed,
      failed,
      successRate: Math.round(((total - failed) / total) * 1000) / 10,
      medianDurationSec: Math.round((3.4 + r() * 1.8) * 10) / 10,
    }
  })
  const runs = buckets.reduce((s, b) => s + b.total, 0)
  const completed = buckets.reduce((s, b) => s + b.completed, 0)
  const per = agents.map((a) => buckets.reduce((s, b) => s + (b.bySeries as Record<string, number>)[a.key], 0))
  const heat = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"].map((day, di) => ({
    day,
    cells: Array.from({ length: 12 }, (_, h) => {
      const biz = h >= 4 && h <= 8 ? 1 : h === 3 || h === 9 ? 0.55 : 0.12
      return Math.round(biz * (di >= 5 ? 0.35 : 1) * (0.55 + r() * 0.45) * 12)
    }),
  }))
  return {
    range: "7d",
    generatedAt: new Date().toISOString(),
    weekly: false,
    totals: {
      runs,
      completed,
      failed: runs - completed,
      successRate: Math.round((completed / runs) * 1000) / 10,
      medianDurationSec: 4.3,
      hoursSaved: Math.round(((completed * 4) / 60) * 10) / 10,
      modelSpendUsd: 6.24,
      decisionsResolved: 9,
      modelCount: 2,
      agentCount: 7,
    },
    deltas: { runs: 12.1, successRate: 0.4, medianDurationSec: -4.2, hoursSaved: 6.5, modelSpendUsd: 3.1, decisionsResolved: 12.5 },
    series: agents.map((a, i) => ({
      key: a.key,
      agentId: a.key,
      name: a.name,
      model: a.model,
      runs: per[i],
      completed: Math.round(per[i] * 0.96),
      failed: per[i] - Math.round(per[i] * 0.96),
      successRate: [97.5, 95.6, 93.9][i],
      latencyP50Sec: a.lat,
      lastRunAt: new Date(Date.now() - [2, 14, 60][i] * 60000).toISOString(),
      spark: Array.from({ length: 12 }, () => Math.round(2 + r() * 8)),
    })),
    buckets,
    heat,
    utilization: { percent: 38, executingHours: 447, idleHours: 729, agentCount: 7 },
    funnel: [
      { key: "outreach_enrolled", name: "Enrolled in sequence", value: 38 },
      { key: "meeting_follow_up_prepared", name: "Engaged", value: 21 },
      { key: "lead_qualified", name: "Qualified", value: 8 },
      { key: "opportunity_created", name: "Meeting booked", value: 3 },
    ],
  }
}
