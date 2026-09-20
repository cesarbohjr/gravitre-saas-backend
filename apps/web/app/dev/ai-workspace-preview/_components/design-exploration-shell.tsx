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
  SelectedSettings,
  SelectedMarketplace,
  SelectedWorkflows,
} from "./selected-ops"
import { FoundationPrototype } from "./ux30-plus/foundation-prototype"
import { IntelligenceFieldPrototype } from "./ux30-plus/intelligence-field-prototype"
import { ActivityTracePrototype } from "./ux30-plus/activity-trace-prototype"
import { NavRailPrototype } from "./ux30-plus/nav-rail-prototype"

const UX30_SURFACES = ["foundation", "intelligence", "activity", "navigation"] as const
type Ux30Surface = (typeof UX30_SURFACES)[number]

const LEGACY_SURFACES = [
  "nucleo",
  "ai",
  "agents",
  "relationships",
  "performance",
  "workflows",
  "runs",
  "connectors",
  "approvals",
  "settings",
  "marketplace",
] as const
type LegacySurface = (typeof LEGACY_SURFACES)[number]

type Surface = Ux30Surface | LegacySurface

const UX30_SCENES: Record<Ux30Surface, string[]> = {
  foundation: ["default", "reduced"],
  intelligence: ["default", "selected", "inspector", "ai-context", "loading", "empty", "error", "mobile", "reduced"],
  activity: [
    "default",
    "selected",
    "inspector",
    "ai-context",
    "loading",
    "empty",
    "error",
    "mobile",
    "reduced",
    "timeline",
    "fail",
  ],
  navigation: ["compact", "expanded", "pinned", "keyboard", "mobile"],
}

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
  const raw = params.get("s") ?? "foundation"
  const isUx30 = (UX30_SURFACES as readonly string[]).includes(raw)
  const surface = (isUx30 ? raw : raw) as Surface
  const scene = params.get("scene") ?? defaultScene(surface)

  const href = (s: Surface, sc?: string) => {
    const next = sc ?? defaultScene(s)
    return `/dev/ai-workspace-preview?s=${s}&scene=${encodeURIComponent(next)}`
  }

  const scenes = useMemo(() => {
    if ((UX30_SURFACES as readonly string[]).includes(surface)) {
      return UX30_SCENES[surface as Ux30Surface]
    }
    if (surface === "ai") return AI_SCENES
    return [...OPS_SCENES]
  }, [surface])

  return (
    <div className="min-h-screen bg-[color:var(--g-background)] text-[color:var(--g-text-primary)]">
      <header className="border-b border-[color:var(--g-border-default)] bg-[color:var(--g-canvas)] px-4 py-3 md:px-6">
        <p className={TYPE.eyebrow}>UX/UI 3.0 Plus · harness only · not production</p>
        <h1 className={TYPE.pageTitle}>Design exploration — Cesar selection prototypes</h1>
        <nav className="mt-3 flex flex-wrap gap-1" aria-label="3.0 Plus surfaces">
          {UX30_SURFACES.map((s) => (
            <Button key={s} size="sm" variant={surface === s ? "secondary" : "default"} asChild>
              <a href={href(s)}>{s}</a>
            </Button>
          ))}
        </nav>
        <nav className="mt-2 flex flex-wrap gap-1" aria-label="Legacy Reset 2.0 surfaces">
          {LEGACY_SURFACES.map((s) => (
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
        {surface === "foundation" && <FoundationPrototype scene={scene} />}
        {surface === "intelligence" && <IntelligenceFieldPrototype scene={scene} />}
        {surface === "activity" && <ActivityTracePrototype scene={scene} />}
        {surface === "navigation" && <NavRailPrototype scene={scene} />}
        {surface === "nucleo" && <SelectedNucleo scene={scene} />}
        {surface === "ai" && <SelectedAiCommandOs scene={normalizeAi(scene)} />}
        {surface === "agents" && <SelectedAgents scene={scene} />}
        {surface === "relationships" && <SelectedRelationships scene={scene} />}
        {surface === "performance" && <SelectedPerformance scene={scene} />}
        {surface === "workflows" && <SelectedWorkflows scene={scene} />}
        {surface === "runs" && <SelectedRuns scene={scene === "selected" ? "trace" : scene} />}
        {surface === "connectors" && <SelectedConnectors scene={scene} />}
        {surface === "approvals" && <SelectedApprovals scene={scene} />}
        {surface === "settings" && <SelectedSettings scene={scene} />}
        {surface === "marketplace" && <SelectedMarketplace scene={scene} />}
      </main>
    </div>
  )
}

function defaultScene(surface: Surface): string {
  if (surface === "foundation") return "default"
  if (surface === "intelligence") return "default"
  if (surface === "activity") return "default"
  if (surface === "navigation") return "compact"
  if (surface === "ai") return "compact-conversation"
  if (surface === "agents") return "default"
  return "default"
}

function normalizeAi(scene: string): AiScene {
  return (AI_SCENES as string[]).includes(scene) ? (scene as AiScene) : "compact-conversation"
}
