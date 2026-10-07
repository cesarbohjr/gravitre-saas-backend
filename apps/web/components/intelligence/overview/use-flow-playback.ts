"use client"

import { useEffect, useReducer, useRef } from "react"
import {
  edgeKey,
  type FlowEvent,
  type FlowModel,
} from "@/components/intelligence/overview/flow-model"
import {
  EXAMPLE_FEEDBACK,
  EXAMPLE_FORWARD,
  EXAMPLE_NODE_IDS,
  EXAMPLE_REINFORCED,
  EXAMPLE_START,
  type ExampleScenario,
} from "@/components/intelligence/overview/example-flow"

/**
 * Animation state for the flow map. In live mode a moving dot is always one
 * real event (an outcome Gravitre recorded in the last few minutes, or one
 * that arrived on a refresh); nothing is spawned for show. Example mode runs
 * the design's example scenarios and keeps its own example counters.
 */

export type Journey = { id: string; path: string[]; feedback: boolean; i: number; t: number; done?: boolean }

type Sim = {
  mode: "example" | "live"
  journeys: Journey[]
  act: Record<string, number>
  boost: Record<string, number>
  events: FlowEvent[]
  queue: FlowEvent[]
  seen: Set<string>
  primed: boolean
  signals: number
  strength: number
  outcomes: number
  rein: Record<string, number>
  sig: Record<string, number>
  spawnIn: number
  seq: number
  last: ExampleScenario | null
}

const STEP_MS = 820
const FRESH_MS = 15 * 60_000

function createSim(mode: "example" | "live"): Sim {
  const now = Date.now()
  const seed = mode === "example" ? [EXAMPLE_FORWARD[3], EXAMPLE_FEEDBACK[0], EXAMPLE_FORWARD[1]] : []
  const sig: Record<string, number> = {}
  if (mode === "example") EXAMPLE_NODE_IDS.forEach((id, i) => (sig[id] = 20 + ((i * 53) % 90)))
  return {
    mode,
    journeys: [],
    act: {},
    boost: {},
    events: seed.map((s, i) => ({
      id: `seed${i}`,
      text: s.text,
      path: s.path,
      tone: s.feedback ? "feedback" : "forward",
      at: new Date(now - (i + 1) * 6000).toISOString(),
    })),
    queue: [],
    seen: new Set(),
    primed: false,
    signals: EXAMPLE_START.signals,
    strength: 0,
    outcomes: EXAMPLE_START.outcomes,
    rein: { ...EXAMPLE_REINFORCED },
    sig,
    spawnIn: 200,
    seq: 0,
    last: null,
  }
}

export type FlowPlayback = {
  journeys: Journey[]
  act: Record<string, number>
  /** Extra edge weight earned this session, by edge key. */
  boost: Record<string, number>
  inFlight: number
  /** Example mode only: generated example events and counters. */
  exampleEvents: FlowEvent[]
  exampleSignals: number
  exampleStrength: number
  exampleOutcomes: number
  exampleReinforced: Record<string, number>
  exampleNodeSignals: Record<string, number>
  /** Wall-clock time of the last frame, for "ago" labels. */
  now: number
}

export function useFlowPlayback(
  model: FlowModel,
  { paused, speed }: { paused: boolean; speed: number },
): FlowPlayback {
  const mode = model.example ? "example" : "live"
  const simRef = useRef<Sim>(createSim(mode))
  const [, rerender] = useReducer((n: number) => n + 1, 0)
  const live = useRef({ paused, speed })
  live.current = { paused, speed }

  if (simRef.current.mode !== mode) simRef.current = createSim(mode)

  // Live: queue real events with a path. First load plays only fresh ones; later refreshes play anything new.
  useEffect(() => {
    const sim = simRef.current
    if (sim.mode !== "live") return
    const now = Date.now()
    for (const e of [...model.events].reverse()) {
      if (sim.seen.has(e.id)) continue
      sim.seen.add(e.id)
      if (e.path.length < 2) continue
      const at = Date.parse(e.at ?? "")
      if (!sim.primed && !(Number.isFinite(at) && now - at <= FRESH_MS)) continue
      sim.queue.push(e)
    }
    sim.primed = true
  }, [model.events, mode])

  useEffect(() => {
    let last = Date.now()
    let lastPaint = 0
    const timer = window.setInterval(() => {
      const sim = simRef.current
      const now = Date.now()
      const dt = Math.min(100, now - last)
      last = now
      const { paused: isPaused, speed: s } = live.current
      const busy = sim.journeys.length > 0 || sim.queue.length > 0 || sim.mode === "example"
      if (!isPaused && busy) {
        step(sim, dt * s)
        rerender()
      } else if (now - lastPaint > 1000) {
        lastPaint = now
        rerender()
      }
    }, 40)
    return () => window.clearInterval(timer)
  }, [])

  const sim = simRef.current
  return {
    journeys: sim.journeys,
    act: sim.act,
    boost: sim.boost,
    inFlight: sim.journeys.length,
    exampleEvents: sim.events,
    exampleSignals: sim.signals,
    exampleStrength: sim.strength,
    exampleOutcomes: sim.outcomes,
    exampleReinforced: sim.rein,
    exampleNodeSignals: sim.sig,
    now: Date.now(),
  }
}

function spawnExample(sim: Sim) {
  sim.seq += 1
  const feedback = sim.seq % 3 === 0
  const list = feedback ? EXAMPLE_FEEDBACK : EXAMPLE_FORWARD
  let scenario = list[Math.floor(Math.random() * list.length)]
  if (scenario === sim.last) scenario = list[(list.indexOf(scenario) + 1) % list.length]
  sim.last = scenario
  const id = `j${sim.seq}`
  sim.journeys.push({ id, path: scenario.path, feedback, i: 0, t: 0 })
  sim.act[scenario.path[0]] = 1
  sim.events.unshift({ id, text: scenario.text, path: scenario.path, tone: feedback ? "feedback" : "forward", at: new Date().toISOString() })
  if (sim.events.length > 7) sim.events.length = 7
}

function spawnLive(sim: Sim) {
  const e = sim.queue.shift()
  if (!e) return
  sim.journeys.push({ id: e.id, path: e.path, feedback: e.tone === "feedback", i: 0, t: 0 })
  sim.act[e.path[0]] = 1
}

function step(sim: Sim, dt: number) {
  sim.spawnIn -= dt
  if (sim.spawnIn <= 0) {
    if (sim.mode === "example") {
      spawnExample(sim)
      sim.spawnIn = 650 + Math.random() * 650
    } else if (sim.queue.length) {
      spawnLive(sim)
      sim.spawnIn = 700
    } else {
      sim.spawnIn = 0
    }
  }
  for (const j of sim.journeys) {
    j.t += dt / STEP_MS
    while (j.t >= 1 && !j.done) {
      j.t -= 1
      j.i += 1
      const node = j.path[j.i]
      const key = edgeKey(j.path[j.i - 1], node)
      const rev = edgeKey(node, j.path[j.i - 1])
      sim.act[node] = 1
      sim.boost[key] = Math.min(3, (sim.boost[key] ?? 0) + 0.1)
      sim.boost[rev] = Math.min(3, (sim.boost[rev] ?? 0) + 0.1)
      if (sim.mode === "example") {
        sim.sig[node] = (sim.sig[node] ?? 0) + 1
        sim.signals += 1
        sim.strength += 1
        if (node in sim.rein) sim.rein[node] += 1
      }
      if (j.i >= j.path.length - 1) {
        j.done = true
        if (sim.mode === "example" && j.feedback && sim.outcomes < EXAMPLE_START.target) sim.outcomes += 1
      }
    }
  }
  sim.journeys = sim.journeys.filter((j) => !j.done)
  const decay = Math.exp(-dt / 650)
  for (const k of Object.keys(sim.act)) sim.act[k] *= decay
}
