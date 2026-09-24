"use client"

/**
 * Docked Gravitre Window Manager concept — harness only.
 * Modes: compact / floating / docked / expanded / fullscreen / minimized.
 * Fixture conversation + task state — no remount of production chat runtime.
 */

import { useState } from "react"
import { Button } from "@/components/ui/button"
import { TYPE } from "@/lib/design-system"
import { cn } from "@/lib/utils"
import { HarnessSurface } from "./topology-primitives"

type WmMode = "compact" | "floating" | "docked" | "expanded" | "fullscreen" | "minimized"

const MODES: WmMode[] = ["compact", "floating", "docked", "expanded", "fullscreen", "minimized"]

const FIXTURE = {
  conversation: "Qualify Acme inbound and open HubSpot contact if SQL.",
  task: "Qualify lead · HubSpot create",
  progress: "2/4 steps",
  voice: "idle",
  approval: "waiting · Approve outreach",
  artifact: "Contact draft · Acme Corp",
}

function compositionFor(mode: WmMode) {
  switch (mode) {
    case "compact":
      return ["conversation", "task", "progress", "primary action"]
    case "floating":
      return ["conversation", "artifact preview", "execution", "approval", "resize"]
    case "docked":
      return ["conversation", "task rail", "artifact strip", "execution status", "page context visible"]
    case "expanded":
      return ["conversation", "artifact", "task", "approval", "supporting context"]
    case "fullscreen":
      return ["conversation", "artifact workspace", "inspector", "execution", "sources"]
    case "minimized":
      return ["task chip", "progress", "restore"]
  }
}

export function WindowManagerDockedPrototype({ scene }: { scene: string }) {
  const initial = (MODES.find((m) => scene.includes(m)) ?? "docked") as WmMode
  const [mode, setMode] = useState<WmMode>(initial)

  return (
    <div data-review-surface="window-manager" data-review-scene={scene} className="mx-auto max-w-6xl space-y-4">
      <header>
        <p className={TYPE.eyebrow}>3.0 Plus · Window Manager · harness only</p>
        <h2 className={cn(TYPE.pageTitle, "mt-1")}>Docked mode concept (state-preserving compositions)</h2>
        <p className={cn(TYPE.pageLead, "mt-2")}>
          Structural variants for Cesar selection. Fixture AI state only — does not remount production{" "}
          <code className="font-mono text-xs">useChat</code> / workspace provider.
        </p>
      </header>

      <div className="flex flex-wrap gap-1">
        {MODES.map((m) => (
          <Button key={m} size="sm" variant={mode === m ? "secondary" : "ghost"} onClick={() => setMode(m)}>
            {m}
          </Button>
        ))}
      </div>

      <div
        className={cn(
          "relative min-h-[360px] rounded-xl border border-[color:var(--g-border-default)] bg-[color:var(--g-canvas)] p-3",
          mode === "fullscreen" && "min-h-[520px] p-0",
        )}
      >
        {mode !== "fullscreen" && mode !== "minimized" ? (
          <div className="mb-3 rounded-lg border border-dashed border-[color:var(--g-border-subtle)] bg-[color:var(--g-surface-1)]/50 p-4">
            <p className={TYPE.eyebrow}>Underlying page (visible in docked)</p>
            <p className={cn(TYPE.cardTitle, "mt-1")}>Intelligence · Field primary</p>
            <p className={TYPE.meta}>Page context remains when WM is docked — not a modal takeover.</p>
          </div>
        ) : null}

        {mode === "minimized" ? (
          <button
            type="button"
            className="absolute bottom-4 right-4 flex items-center gap-2 rounded-full border border-[color:var(--g-border-default)] bg-[color:var(--g-surface-1)] px-3 py-2 text-xs shadow-sm"
            onClick={() => setMode("docked")}
          >
            <span className="font-medium">{FIXTURE.task}</span>
            <span className="text-[color:var(--g-text-muted)]">{FIXTURE.progress}</span>
          </button>
        ) : (
          <div
            className={cn(
              "border border-[color:var(--g-border-default)] bg-[color:var(--g-surface-1)] shadow-sm",
              mode === "compact" && "ml-auto w-full max-w-sm rounded-xl p-3",
              mode === "floating" && "absolute right-6 top-16 w-[360px] rounded-xl p-3",
              mode === "docked" && "flex w-full max-w-md flex-col rounded-xl border-l-2 border-l-[color:var(--g-brand)] p-0 md:absolute md:bottom-3 md:right-3 md:top-24",
              mode === "expanded" && "mx-auto w-full max-w-3xl rounded-xl p-4",
              mode === "fullscreen" && "flex h-full min-h-[520px] flex-col rounded-none p-4",
            )}
            data-wm-mode={mode}
          >
            <div className="flex items-center justify-between gap-2 border-b border-[color:var(--g-border-subtle)] px-3 py-2">
              <p className={TYPE.eyebrow}>Gravitre · {mode}</p>
              <div className="flex gap-1">
                <Button size="sm" variant="ghost" onClick={() => setMode("minimized")}>
                  min
                </Button>
                <Button size="sm" variant="ghost" onClick={() => setMode(mode === "docked" ? "floating" : "docked")}>
                  {mode === "docked" ? "undock" : "dock"}
                </Button>
              </div>
            </div>
            <div className={cn("space-y-3 p-3", mode === "fullscreen" && "grid flex-1 gap-3 md:grid-cols-[1fr_1fr_240px]")}>
              <HarnessSurface className="p-3">
                <p className={TYPE.eyebrow}>Conversation</p>
                <p className="mt-1 text-sm">{FIXTURE.conversation}</p>
              </HarnessSurface>
              {(mode === "docked" || mode === "expanded" || mode === "fullscreen" || mode === "floating") && (
                <HarnessSurface className="p-3">
                  <p className={TYPE.eyebrow}>Artifact</p>
                  <p className="mt-1 text-sm">{FIXTURE.artifact}</p>
                </HarnessSurface>
              )}
              {(mode === "expanded" || mode === "fullscreen" || mode === "docked") && (
                <HarnessSurface className="p-3">
                  <p className={TYPE.eyebrow}>Task / execution</p>
                  <p className="mt-1 text-sm">{FIXTURE.task}</p>
                  <p className={TYPE.meta}>{FIXTURE.progress} · voice {FIXTURE.voice}</p>
                  <p className="mt-2 text-xs text-[color:var(--g-warning)]">{FIXTURE.approval}</p>
                </HarnessSurface>
              )}
              {mode === "compact" && (
                <div className="flex items-center justify-between gap-2">
                  <p className={TYPE.meta}>{FIXTURE.task} · {FIXTURE.progress}</p>
                  <Button size="sm">Continue</Button>
                </div>
              )}
              {mode === "fullscreen" && (
                <HarnessSurface className="p-3 md:col-span-1">
                  <p className={TYPE.eyebrow}>Inspector / sources</p>
                  <p className={TYPE.meta}>Evidence slots — not simulated browser use</p>
                </HarnessSurface>
              )}
            </div>
          </div>
        )}
      </div>

      <HarnessSurface className="p-4">
        <p className={TYPE.eyebrow}>Composition for {mode}</p>
        <p className="mt-2 text-sm">{compositionFor(mode).join(" · ")}</p>
        <p className={cn(TYPE.meta, "mt-2")}>
          Must survive transitions: conversation, artifacts, agent task, workflow context, voice, approval, execution,
          inspector selection — production wiring deferred until G-STRUCT.
        </p>
      </HarnessSurface>
    </div>
  )
}
