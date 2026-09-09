import type { DepartmentId, NetworkScenario } from "./types"

/**
 * Configuration-driven converge stories.
 * Work starts anywhere → Gravitre connects context → teams act → results return → business learns.
 */

export const NETWORK_SCENARIOS: NetworkScenario[] = [
  {
    id: "sales-support",
    label: "Sales → Support",
    source: "sales",
    beats: [
      { type: "activate", dept: "sales", caption: "Sales creates a signal.", durationMs: 700 },
      {
        type: "packet",
        from: "sales",
        to: "core",
        kind: "signal",
        caption: "Gravitre receives context.",
        durationMs: 1100,
      },
      { type: "core", state: "connecting", caption: "Gravitre connects the context.", durationMs: 900 },
      {
        type: "packet",
        from: "core",
        to: "support",
        kind: "action",
        caption: "Support receives what it needs.",
        durationMs: 1100,
      },
      { type: "resolve", dept: "support", durationMs: 600 },
      {
        type: "packet",
        from: "support",
        to: "core",
        kind: "learn",
        caption: "The outcome returns.",
        durationMs: 1000,
      },
      { type: "core", state: "verified", durationMs: 700 },
      { type: "core", state: "learned", caption: "The shared intelligence improves.", durationMs: 900 },
      { type: "settle", durationMs: 800 },
    ],
  },
  {
    id: "support-sales",
    label: "Support → Sales",
    source: "support",
    beats: [
      { type: "activate", dept: "support", caption: "Support creates a signal.", durationMs: 700 },
      {
        type: "packet",
        from: "support",
        to: "core",
        kind: "signal",
        caption: "Gravitre receives context.",
        durationMs: 1100,
      },
      { type: "core", state: "connecting", caption: "Gravitre connects the context.", durationMs: 900 },
      {
        type: "packet",
        from: "core",
        to: "sales",
        kind: "action",
        caption: "Sales receives what it needs.",
        durationMs: 1100,
      },
      { type: "resolve", dept: "sales", durationMs: 600 },
      {
        type: "packet",
        from: "sales",
        to: "core",
        kind: "learn",
        caption: "The outcome returns.",
        durationMs: 1000,
      },
      { type: "core", state: "learned", caption: "The shared intelligence improves.", durationMs: 900 },
      { type: "settle", durationMs: 800 },
    ],
  },
  {
    id: "sales-many",
    label: "Sales → Finance + Ops",
    source: "sales",
    beats: [
      { type: "activate", dept: "sales", caption: "Sales creates a signal.", durationMs: 700 },
      {
        type: "packet",
        from: "sales",
        to: "core",
        kind: "signal",
        caption: "Gravitre receives context.",
        durationMs: 1100,
      },
      { type: "core", state: "coordinating", caption: "Gravitre coordinates the teams.", durationMs: 900 },
      {
        type: "packet",
        from: "core",
        to: "finance",
        kind: "action",
        caption: "Finance works from the same intelligence.",
        durationMs: 1000,
      },
      {
        type: "packet",
        from: "core",
        to: "operations",
        kind: "action",
        caption: "Operations acts in parallel.",
        durationMs: 1000,
      },
      { type: "resolve", dept: "finance", durationMs: 400 },
      { type: "resolve", dept: "operations", durationMs: 400 },
      {
        type: "packet",
        from: "finance",
        to: "core",
        kind: "learn",
        caption: "The outcome returns.",
        durationMs: 900,
      },
      {
        type: "packet",
        from: "operations",
        to: "core",
        kind: "learn",
        durationMs: 900,
      },
      { type: "core", state: "learned", caption: "The shared intelligence improves.", durationMs: 900 },
      { type: "settle", durationMs: 800 },
    ],
  },
  {
    id: "cross-loop",
    label: "Support → Sales → Finance",
    source: "support",
    beats: [
      { type: "activate", dept: "support", caption: "Support creates a signal.", durationMs: 650 },
      { type: "packet", from: "support", to: "core", kind: "signal", durationMs: 1000 },
      { type: "core", state: "connecting", caption: "Gravitre connects the context.", durationMs: 800 },
      {
        type: "packet",
        from: "core",
        to: "sales",
        kind: "action",
        caption: "Sales receives what it needs.",
        durationMs: 1000,
      },
      { type: "resolve", dept: "sales", durationMs: 500 },
      { type: "packet", from: "sales", to: "core", kind: "learn", durationMs: 900 },
      { type: "core", state: "coordinating", durationMs: 700 },
      {
        type: "packet",
        from: "core",
        to: "finance",
        kind: "action",
        caption: "Finance works from the same intelligence.",
        durationMs: 1000,
      },
      { type: "resolve", dept: "finance", durationMs: 500 },
      {
        type: "packet",
        from: "finance",
        to: "core",
        kind: "learn",
        caption: "The shared intelligence improves.",
        durationMs: 900,
      },
      { type: "core", state: "learned", durationMs: 800 },
      { type: "settle", durationMs: 800 },
    ],
  },
]

export function scenariosForSource(source: DepartmentId): NetworkScenario[] {
  return NETWORK_SCENARIOS.filter((s) => s.source === source)
}

export function nextScenarioIndex(current: number): number {
  return (current + 1) % NETWORK_SCENARIOS.length
}
