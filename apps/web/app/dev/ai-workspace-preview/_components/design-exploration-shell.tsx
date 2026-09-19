"use client"

import { useMemo } from "react"
import { useSearchParams } from "next/navigation"
import { Button } from "@/components/ui/button"
import { TYPE } from "@/lib/design-system"
import { SelectedAiCommandOs, type AiScene } from "./selected-ai"
import {
  SelectedAgents,
  SelectedApprovals,
  SelectedConnectors,
  SelectedNucleo,
  SelectedPerformance,
  SelectedRelationships,
  SelectedRuns,
  SelectedWorkflows,
} from "./selected-ops"

const SURFACES = ["nucleo", "ai", "agents", "relationships", "performance", "workflows", "runs", "connectors", "approvals"] as const
type Surface = (typeof SURFACES)[number]

const AI_SCENES: AiScene[] = [
  "empty",
  "loading",
  "error",
  "compact-conversation",
  "compact-voice-listen",
  "compact-voice-speak",
  "expanded-conversation",
  "expanded-history",
  "expanded-work",
  "expanded-tool",
  "fullscreen-work",
  "fullscreen-inspect",
  "mobile-conversation",
  "mobile-work",
  "mobile-inspect",
]

const OPS_SCENES = ["default", "empty", "loading", "error", "selected", "list", "graph", "mobile"] as const

export function DesignExplorationShell() {
  const params = useSearchParams()
  const surface = (SURFACES.find((s) => s === params.get("s")) ?? "ai") as Surface
  const scene = params.get("scene") ?? defaultScene(surface)

  const href = (s: Surface, sc?: string) => {
    const next = sc ?? defaultScene(s)
    return `/dev/ai-workspace-preview?s=${s}&scene=${encodeURIComponent(next)}`
  }

  const scenes = useMemo(() => (surface === "ai" ? AI_SCENES : [...OPS_SCENES]), [surface])

  return (
    <div className="min-h-screen bg-[color:var(--g-background)] text-[color:var(--g-text-primary)]">
      <header className="border-b border-[color:var(--g-border-default)] bg-[color:var(--g-canvas)] px-4 py-3 md:px-6">
        <p className={TYPE.eyebrow}>UX Reset 2.0 · selected directions · mock only · not production</p>
        <h1 className={TYPE.pageTitle}>Final visual review harness</h1>
        <nav className="mt-3 flex flex-wrap gap-1" aria-label="Surfaces">
          {SURFACES.map((s) => (
            <Button key={s} size="sm" variant={surface === s ? "secondary" : "ghost"} asChild>
              <a href={href(s)}>{s}</a>
            </Button>
          ))}
        </nav>
        <nav className="mt-2 flex flex-wrap gap-1" aria-label="Scenes">
          {scenes.map((sc) => (
            <Button key={sc} size="sm" variant={scene === sc ? "secondary" : "ghost"} asChild>
              <a href={href(surface, sc)}>{sc}</a>
            </Button>
          ))}
        </nav>
      </header>
      <main className="p-4 md:p-6">
        {surface === "nucleo" && <SelectedNucleo scene={scene} />}
        {surface === "ai" && <SelectedAiCommandOs scene={normalizeAi(scene)} />}
        {surface === "agents" && <SelectedAgents scene={scene} />}
        {surface === "relationships" && <SelectedRelationships scene={scene} />}
        {surface === "performance" && <SelectedPerformance scene={scene} />}
        {surface === "workflows" && <SelectedWorkflows scene={scene} />}
        {surface === "runs" && (
          <SelectedRuns scene={scene === "selected" ? "trace" : scene} />
        )}
        {surface === "connectors" && <SelectedConnectors scene={scene} />}
        {surface === "approvals" && <SelectedApprovals scene={scene} />}
      </main>
    </div>
  )
}

function defaultScene(surface: Surface): string {
  if (surface === "ai") return "compact-conversation"
  if (surface === "agents") return "default"
  return "default"
}

function normalizeAi(scene: string): AiScene {
  return (AI_SCENES as string[]).includes(scene) ? (scene as AiScene) : "compact-conversation"
}
