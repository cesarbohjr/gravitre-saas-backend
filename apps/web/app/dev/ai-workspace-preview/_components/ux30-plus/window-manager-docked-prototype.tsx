"use client"

/**
 * Window Manager selection package — modes + transitions + stable fixture ids.
 * Harness only · fixture conversation/task — not production execution.
 */

import { useEffect, useState } from "react"
import { Button } from "@/components/ui/button"
import { TYPE } from "@/lib/design-system"
import { cn } from "@/lib/utils"
import { HarnessSurface } from "./topology-primitives"

type WmMode = "compact" | "floating" | "docked" | "expanded" | "fullscreen" | "minimized" | "restored"

const MODES: WmMode[] = ["compact", "floating", "docked", "expanded", "fullscreen", "minimized", "restored"]

/** Stable across mode transitions — proves no new conversation on mode change. */
const FIXTURE = {
  conversationId: "conv_fixture_3plus_001",
  taskId: "task_fixture_qualify_acme",
  conversation: "Qualify Acme inbound and open HubSpot contact if SQL.",
  task: "Qualify lead · HubSpot create",
  progress: "2/4 steps",
  voice: "idle",
  approval: "waiting · Approve outreach",
  artifact: "Contact draft · Acme Corp",
}

const DEFAULT_PROPOSAL: WmMode = "docked"

function compositionFor(mode: WmMode) {
  switch (mode) {
    case "compact":
      return ["conversation", "task", "progress", "primary action", "voice if active"]
    case "floating":
      return ["conversation", "artifact preview", "execution", "approval", "resize"]
    case "docked":
      return ["conversation", "task rail", "artifact strip", "execution", "page context visible"]
    case "expanded":
      return ["conversation", "artifact", "task", "approval", "supporting context"]
    case "fullscreen":
      return ["conversation", "artifact workspace", "inspector", "execution", "sources"]
    case "minimized":
      return ["task chip", "progress", "restore"]
    case "restored":
      return ["returns to last non-minimized composition"]
  }
}

export function WindowManagerDockedPrototype({ scene }: { scene: string }) {
  const tour = scene.includes("tour")
  const initialRaw = (MODES.find((m) => scene.includes(m)) ?? "docked") as WmMode
  const [mode, setMode] = useState<WmMode>(initialRaw === "restored" ? "docked" : initialRaw)
  const [lastMode, setLastMode] = useState<WmMode>("docked")
  const [transitionLog, setTransitionLog] = useState<string[]>([
    `init · ${FIXTURE.conversationId} · ${FIXTURE.taskId}`,
  ])

  useEffect(() => {
    if (!tour) return
    const order: WmMode[] = ["compact", "floating", "docked", "expanded", "fullscreen", "minimized", "restored"]
    let i = 0
    const id = window.setInterval(() => {
      const next = order[i % order.length]
      setMode((prev) => {
        if (prev !== "minimized" && next === "minimized") setLastMode(prev)
        if (next === "restored") return lastMode
        return next
      })
      setTransitionLog((log) =>
        [`${next} · ${FIXTURE.conversationId} unchanged`, ...log].slice(0, 8),
      )
      i += 1
    }, 1600)
    return () => window.clearInterval(id)
  }, [tour, lastMode])

  const applyMode = (next: WmMode) => {
    setMode((prev) => {
      if (prev !== "minimized" && next === "minimized") setLastMode(prev)
      if (next === "restored") {
        setTransitionLog((log) =>
          [`restored→${lastMode} · ${FIXTURE.conversationId} unchanged`, ...log].slice(0, 8),
        )
        return lastMode
      }
      setTransitionLog((log) =>
        [`${prev}→${next} · ${FIXTURE.conversationId} unchanged`, ...log].slice(0, 8),
      )
      return next
    })
  }

  const displayMode = mode

  return (
    <div data-review-surface="window-manager" data-review-scene={scene} className="mx-auto max-w-6xl space-y-4">
      <header>
        <p className={TYPE.eyebrow}>Selection B · Window Manager · harness only</p>
        <h2 className={cn(TYPE.pageTitle, "mt-1")}>Mode compositions & transitions</h2>
        <p className={cn(TYPE.pageLead, "mt-2")}>
          Fixture conversation/task ids stay stable across transitions. Not production chat remount. Proposed default:{" "}
          <strong>docked</strong> (Cesar decides).
        </p>
      </header>

      <div className="flex flex-wrap gap-1">
        {MODES.map((m) => (
          <Button key={m} size="sm" variant={displayMode === m || (m === "restored" && scene.includes("restored")) ? "secondary" : "ghost"} onClick={() => applyMode(m)}>
            {m}
            {m === DEFAULT_PROPOSAL ? " ★" : ""}
          </Button>
        ))}
        <Button size="sm" variant={tour ? "secondary" : "outline"} asChild>
          <a href="/dev/ai-workspace-preview?s=window-manager&scene=tour">Auto tour</a>
        </Button>
      </div>

      <HarnessSurface className="flex flex-wrap gap-4 p-3 text-xs">
        <span>
          conversationId: <code className="font-mono">{FIXTURE.conversationId}</code>
        </span>
        <span>
          taskId: <code className="font-mono">{FIXTURE.taskId}</code>
        </span>
        <span>voice: {FIXTURE.voice}</span>
        <span className="text-[color:var(--g-warning)]">{FIXTURE.approval}</span>
      </HarnessSurface>

      <div
        className={cn(
          "relative min-h-[360px] rounded-xl border border-[color:var(--g-border-default)] bg-[color:var(--g-canvas)] p-3",
          displayMode === "fullscreen" && "min-h-[520px] p-0",
        )}
      >
        {displayMode !== "fullscreen" && displayMode !== "minimized" ? (
          <div className="mb-3 rounded-lg border border-dashed border-[color:var(--g-border-subtle)] bg-[color:var(--g-surface-1)]/50 p-4">
            <p className={TYPE.eyebrow}>Underlying page</p>
            <p className={cn(TYPE.cardTitle, "mt-1")}>Intelligence · Field primary</p>
            <p className={TYPE.meta}>Visible especially when WM is docked — not a modal takeover.</p>
          </div>
        ) : null}

        {displayMode === "minimized" ? (
          <button
            type="button"
            className="absolute bottom-4 right-4 flex items-center gap-2 rounded-full border border-[color:var(--g-border-default)] bg-[color:var(--g-surface-1)] px-3 py-2 text-xs"
            onClick={() => applyMode("restored")}
          >
            <span className="font-medium">{FIXTURE.task}</span>
            <span className="text-[color:var(--g-text-muted)]">{FIXTURE.progress}</span>
          </button>
        ) : (
          <div
            className={cn(
              "border border-[color:var(--g-border-default)] bg-[color:var(--g-surface-1)]",
              displayMode === "compact" && "ml-auto w-full max-w-sm rounded-xl p-3",
              displayMode === "floating" && "absolute right-6 top-16 w-[360px] rounded-xl p-3",
              displayMode === "docked" &&
                "flex w-full max-w-md flex-col rounded-xl border-l-2 border-l-[color:var(--g-brand)] p-0 md:absolute md:bottom-3 md:right-3 md:top-24",
              displayMode === "expanded" && "mx-auto w-full max-w-3xl rounded-xl p-4",
              displayMode === "fullscreen" && "flex h-full min-h-[520px] flex-col rounded-none p-4",
            )}
            data-wm-mode={displayMode}
          >
            <div className="flex items-center justify-between gap-2 border-b border-[color:var(--g-border-subtle)] px-3 py-2">
              <p className={TYPE.eyebrow}>Gravitre · {displayMode}</p>
              <div className="flex gap-1">
                <Button size="sm" variant="ghost" onClick={() => applyMode("minimized")}>
                  min
                </Button>
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() => applyMode(displayMode === "docked" ? "floating" : "docked")}
                >
                  {displayMode === "docked" ? "undock" : "dock"}
                </Button>
              </div>
            </div>
            <div
              className={cn(
                "space-y-3 p-3",
                displayMode === "fullscreen" && "grid flex-1 gap-3 md:grid-cols-[1fr_1fr_240px]",
              )}
            >
              <HarnessSurface className="p-3">
                <p className={TYPE.eyebrow}>Conversation</p>
                <p className="mt-1 text-sm">{FIXTURE.conversation}</p>
              </HarnessSurface>
              {(displayMode === "docked" ||
                displayMode === "expanded" ||
                displayMode === "fullscreen" ||
                displayMode === "floating") && (
                <HarnessSurface className="p-3">
                  <p className={TYPE.eyebrow}>Artifact</p>
                  <p className="mt-1 text-sm">{FIXTURE.artifact}</p>
                </HarnessSurface>
              )}
              {(displayMode === "expanded" || displayMode === "fullscreen" || displayMode === "docked") && (
                <HarnessSurface className="p-3">
                  <p className={TYPE.eyebrow}>Task / execution</p>
                  <p className="mt-1 text-sm">{FIXTURE.task}</p>
                  <p className={TYPE.meta}>
                    {FIXTURE.progress} · voice {FIXTURE.voice}
                  </p>
                  <p className="mt-2 text-xs text-[color:var(--g-warning)]">{FIXTURE.approval}</p>
                </HarnessSurface>
              )}
              {displayMode === "compact" && (
                <div className="flex items-center justify-between gap-2">
                  <p className={TYPE.meta}>
                    {FIXTURE.task} · {FIXTURE.progress}
                  </p>
                  <Button size="sm">Continue</Button>
                </div>
              )}
              {displayMode === "fullscreen" && (
                <HarnessSurface className="p-3">
                  <p className={TYPE.eyebrow}>Inspector / sources</p>
                  <p className={TYPE.meta}>Evidence slots — not simulated browser use</p>
                </HarnessSurface>
              )}
            </div>
          </div>
        )}
      </div>

      <div className="grid gap-3 md:grid-cols-2">
        <HarnessSurface className="p-4">
          <p className={TYPE.eyebrow}>Composition · {displayMode}</p>
          <p className="mt-2 text-sm">{compositionFor(displayMode).join(" · ")}</p>
        </HarnessSurface>
        <HarnessSurface className="p-4">
          <p className={TYPE.eyebrow}>Transition log (stable ids)</p>
          <ul className="mt-2 space-y-1 font-mono text-[11px] text-[color:var(--g-text-secondary)]">
            {transitionLog.map((line) => (
              <li key={line}>{line}</li>
            ))}
          </ul>
        </HarnessSurface>
      </div>

      <HarnessSurface className="p-4">
        <p className={TYPE.eyebrow}>Proposed default · docked</p>
        <p className="mt-2 text-sm">
          Pros: keeps expert page visible; AI assists without takeover; matches MSP multi-tasking. Cons: less immersive
          than fullscreen for deep artifact work; needs careful width. Floating better for quick drag; compact for
          secondary monitor focus. <strong>Final default reserved for Cesar.</strong>
        </p>
      </HarnessSurface>
    </div>
  )
}
