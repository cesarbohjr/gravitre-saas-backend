"use client"

import { useCallback, useEffect, useRef, useState } from "react"
import { animate } from "framer-motion"
import type { CoreState, DepartmentId, NetworkScenario, PacketKind, PathEndpoint, StoryBeat } from "./types"
import { NETWORK_SCENARIOS, nextScenarioIndex, scenariosForSource } from "./scenarios"
import { bezierPath } from "./paths"

export type ActivePacket = {
  key: string
  from: PathEndpoint
  to: PathEndpoint
  kind: PacketKind
  progress: number
  d: string
}

export type NetworkStoryState = {
  coreState: CoreState
  activeDepts: Set<DepartmentId>
  resolvedDepts: Set<DepartmentId>
  mutedDepts: Set<DepartmentId>
  activeEdges: Map<string, PacketKind>
  packets: ActivePacket[]
  caption: string | null
  running: boolean
  scenarioId: string | null
}

export const NETWORK_STORY_IDLE: NetworkStoryState = {
  coreState: "idle",
  activeDepts: new Set(),
  resolvedDepts: new Set(),
  mutedDepts: new Set(),
  activeEdges: new Map(),
  packets: [],
  caption: null,
  running: false,
  scenarioId: null,
}

export function edgeKey(a: PathEndpoint, b: PathEndpoint) {
  return [a, b].sort().join("--")
}

function wait(ms: number, signal: AbortSignal) {
  return new Promise<void>((resolve, reject) => {
    if (signal.aborted) {
      reject(new DOMException("aborted", "AbortError"))
      return
    }
    const t = window.setTimeout(resolve, ms)
    signal.addEventListener(
      "abort",
      () => {
        window.clearTimeout(t)
        reject(new DOMException("aborted", "AbortError"))
      },
      { once: true },
    )
  })
}

const ALL_DEPTS: DepartmentId[] = ["sales", "support", "operations", "finance"]

export function useNetworkStory(options: { reduced: boolean }) {
  const { reduced } = options
  const [state, setState] = useState<NetworkStoryState>(NETWORK_STORY_IDLE)
  const abortRef = useRef<AbortController | null>(null)
  const cursorRef = useRef(0)
  const mountedRef = useRef(true)
  const runningLock = useRef(false)

  useEffect(() => {
    mountedRef.current = true
    return () => {
      mountedRef.current = false
      abortRef.current?.abort()
    }
  }, [])

  const patch = useCallback((fn: (prev: NetworkStoryState) => NetworkStoryState) => {
    if (!mountedRef.current) return
    setState(fn)
  }, [])

  const runBeat = useCallback(
    async (beat: StoryBeat, signal: AbortSignal, scenarioId: string) => {
      const duration = beat.durationMs ?? 800

      if (beat.type === "activate") {
        patch((s) => ({
          ...s,
          caption: beat.caption ?? s.caption,
          activeDepts: new Set([...s.activeDepts, beat.dept]),
          mutedDepts: new Set(ALL_DEPTS.filter((d) => d !== beat.dept && !s.resolvedDepts.has(d))),
        }))
        await wait(duration, signal)
        return
      }

      if (beat.type === "core") {
        patch((s) => ({ ...s, coreState: beat.state, caption: beat.caption ?? s.caption }))
        await wait(duration, signal)
        return
      }

      if (beat.type === "resolve") {
        patch((s) => {
          const active = new Set(s.activeDepts)
          active.delete(beat.dept)
          return {
            ...s,
            caption: beat.caption ?? s.caption,
            activeDepts: active,
            resolvedDepts: new Set([...s.resolvedDepts, beat.dept]),
          }
        })
        await wait(duration, signal)
        return
      }

      if (beat.type === "settle") {
        patch(() => ({
          ...NETWORK_STORY_IDLE,
          caption: beat.caption ?? null,
          running: true,
          scenarioId,
        }))
        await wait(duration, signal)
        return
      }

      if (beat.type === "packet") {
        const d = bezierPath(beat.from, beat.to)
        const key = `${beat.from}-${beat.to}-${beat.kind}-${Math.random().toString(36).slice(2, 8)}`
        const ek = edgeKey(beat.from, beat.to)

        patch((s) => {
          const edges = new Map(s.activeEdges)
          edges.set(ek, beat.kind)
          const involved = new Set<DepartmentId>([...s.activeDepts, ...s.resolvedDepts])
          if (beat.from !== "core") involved.add(beat.from)
          if (beat.to !== "core") involved.add(beat.to)
          return {
            ...s,
            caption: beat.caption ?? s.caption,
            activeEdges: edges,
            mutedDepts: new Set(ALL_DEPTS.filter((dept) => !involved.has(dept))),
            packets: [
              ...s.packets.filter((p) => p.key !== key),
              { key, from: beat.from, to: beat.to, kind: beat.kind, progress: 0, d },
            ],
            coreState:
              beat.to === "core" && beat.kind === "signal"
                ? "receiving"
                : beat.from === "core" && beat.kind === "action"
                  ? "acting"
                  : beat.to === "core" && beat.kind === "learn"
                    ? "learning"
                    : s.coreState,
          }
        })

        await new Promise<void>((resolve, reject) => {
          const controls = animate(0, 1, {
            duration: duration / 1000,
            ease: [0.16, 1, 0.3, 1],
            onUpdate: (v) => {
              if (signal.aborted) {
                controls.stop()
                reject(new DOMException("aborted", "AbortError"))
                return
              }
              patch((s) => ({
                ...s,
                packets: s.packets.map((p) => (p.key === key ? { ...p, progress: v } : p)),
              }))
            },
            onComplete: () => resolve(),
          })
          signal.addEventListener(
            "abort",
            () => {
              controls.stop()
              reject(new DOMException("aborted", "AbortError"))
            },
            { once: true },
          )
        })

        patch((s) => ({
          ...s,
          packets: s.packets.filter((p) => p.key !== key),
        }))
      }
    },
    [patch],
  )

  const runScenario = useCallback(
    async (scenario: NetworkScenario) => {
      if (reduced) return
      abortRef.current?.abort()
      const ac = new AbortController()
      abortRef.current = ac
      runningLock.current = true

      patch(() => ({
        ...NETWORK_STORY_IDLE,
        running: true,
        scenarioId: scenario.id,
      }))

      try {
        for (const beat of scenario.beats) {
          if (ac.signal.aborted) break
          await runBeat(beat, ac.signal, scenario.id)
        }
        if (!ac.signal.aborted && mountedRef.current) {
          patch(() => NETWORK_STORY_IDLE)
        }
      } catch (err) {
        if (!(err instanceof DOMException && err.name === "AbortError")) {
          console.error(err)
        }
      } finally {
        runningLock.current = false
      }
    },
    [patch, reduced, runBeat],
  )

  const playFromDepartment = useCallback(
    (dept: DepartmentId) => {
      if (reduced) return
      const matches = scenariosForSource(dept)
      const scenario = matches[0] ?? NETWORK_SCENARIOS[0]
      if (!scenario) return
      const idx = NETWORK_SCENARIOS.findIndex((s) => s.id === scenario.id)
      if (idx >= 0) cursorRef.current = idx
      void runScenario(scenario)
    },
    [reduced, runScenario],
  )

  const playNextAuto = useCallback(async () => {
    if (reduced || runningLock.current) return
    const scenario = NETWORK_SCENARIOS[cursorRef.current] ?? NETWORK_SCENARIOS[0]
    if (!scenario) return
    await runScenario(scenario)
    cursorRef.current = nextScenarioIndex(cursorRef.current)
  }, [reduced, runScenario])

  const setHoverFocus = useCallback(
    (dept: DepartmentId | null) => {
      if (runningLock.current) return
      if (!dept) {
        patch(() => NETWORK_STORY_IDLE)
        return
      }
      patch(() => ({
        ...NETWORK_STORY_IDLE,
        activeDepts: new Set([dept]),
        mutedDepts: new Set(ALL_DEPTS.filter((d) => d !== dept)),
        activeEdges: new Map([[edgeKey(dept, "core"), "signal"]]),
      }))
    },
    [patch],
  )

  return {
    state,
    playFromDepartment,
    playNextAuto,
    setHoverFocus,
    abort: () => abortRef.current?.abort(),
  }
}
