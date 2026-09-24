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
import { CreativeKfPrototype } from "./creative-kf-prototype"
import { WorkflowBuilderRfPrototype } from "./ux30-plus/workflow-builder-rf-prototype"
import { WindowManagerDockedPrototype } from "./ux30-plus/window-manager-docked-prototype"
import { PageIntroVariantsPrototype } from "./ux30-plus/page-intro-variants-prototype"
import { SharedAiWorkspacePrototype } from "./ux30-plus/shared-ai-workspace-prototype"
import { ModelStudioPrototype } from "./ux30-plus/model-studio-prototype"
import { DesignSelectionIndex } from "./ux30-plus/design-selection-index"
import { IntelligenceJourneyPrototype } from "./ux30-plus/intelligence-journey-prototype"
import { DashboardConceptsPrototype } from "./ux30-plus/dashboard-concepts-prototype"
import { AgentWorkspaceConceptsPrototype } from "./ux30-plus/agent-workspace-concepts-prototype"
import { WorkflowGenPreviewPrototype } from "./ux30-plus/workflow-gen-preview-prototype"

const UX30_SURFACES = [
  "selection",
  "page-intro",
  "window-manager",
  "intelligence-journey",
  "intelligence",
  "workflow-rf",
  "workflow-gen",
  "ai-workspace",
  "model-studio",
  "dashboard",
  "agent-workspace",
  "foundation",
  "activity",
  "navigation",
  "creative",
] as const
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
  selection: ["index"],
  foundation: ["default", "reduced"],
  intelligence: [
    "field-primary",
    "default",
    "change",
    "compare",
    "selected",
    "inspector",
    "ai-context",
    "loading",
    "empty",
    "error",
    "mobile",
    "reduced",
  ],
  "intelligence-journey": ["field-primary", "matrix-rail", "split-insight", "journey", "empty"],
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
  creative: ["compare", "workbench", "refined", "pilot3"],
  "workflow-rf": ["design", "live", "explain", "history", "ai-preview"],
  "workflow-gen": ["prompt", "preview", "rf"],
  "window-manager": ["docked", "compact", "floating", "expanded", "fullscreen", "minimized", "restored", "tour"],
  "page-intro": ["operating", "expert", "empty", "immersive", "compare"],
  "ai-workspace": [
    "conversation-primary",
    "work-primary",
    "show-the-work-slot",
    "voice-continuity",
    "split",
  ],
  "model-studio": ["standard", "advanced"],
  dashboard: ["attention-first", "ops-board", "outcome-rail"],
  "agent-workspace": ["roster-detail", "workbench", "mission"],
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
  const raw = params.get("s") ?? "selection"
  const surface = raw as Surface
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
        <p className={TYPE.eyebrow}>UX/UI 3.0 Plus · harness only · not production · not Phase 8</p>
        <h1 className={TYPE.pageTitle}>Design-selection package — Cesar review</h1>
        <nav className="mt-3 flex flex-wrap gap-1" aria-label="Selection surfaces">
          {UX30_SURFACES.map((s) => (
            <Button key={s} size="sm" variant={surface === s ? "secondary" : "default"} asChild>
              <a href={href(s)}>{s}</a>
            </Button>
          ))}
        </nav>
        <nav className="mt-2 flex flex-wrap gap-1" aria-label="Legacy surfaces">
          {LEGACY_SURFACES.map((s) => (
            <Button key={s} size="sm" variant={surface === s ? "secondary" : "ghost"} asChild>
              <a href={href(s)}>{s}</a>
            </Button>
          ))}
        </nav>
        {surface !== "selection" && (
          <nav className="mt-2 flex flex-wrap gap-1" aria-label="Scenes">
            {scenes.map((sc) => (
              <Button key={sc} size="sm" variant={scene === sc ? "secondary" : "ghost"} asChild>
                <a href={href(surface, sc)}>{sc}</a>
              </Button>
            ))}
          </nav>
        )}
      </header>
      <main className="p-4 md:p-6">
        {surface === "selection" && <DesignSelectionIndex />}
        {surface === "foundation" && <FoundationPrototype scene={scene} />}
        {surface === "intelligence" && <IntelligenceFieldPrototype scene={scene} />}
        {surface === "intelligence-journey" && <IntelligenceJourneyPrototype scene={scene} />}
        {surface === "activity" && <ActivityTracePrototype scene={scene} />}
        {surface === "navigation" && <NavRailPrototype scene={scene} />}
        {surface === "creative" && <CreativeKfPrototype scene={scene} />}
        {surface === "workflow-rf" && <WorkflowBuilderRfPrototype scene={scene} />}
        {surface === "workflow-gen" && <WorkflowGenPreviewPrototype scene={scene} />}
        {surface === "window-manager" && <WindowManagerDockedPrototype scene={scene} />}
        {surface === "page-intro" && <PageIntroVariantsPrototype scene={scene} />}
        {surface === "ai-workspace" && <SharedAiWorkspacePrototype scene={scene} />}
        {surface === "model-studio" && <ModelStudioPrototype scene={scene} />}
        {surface === "dashboard" && <DashboardConceptsPrototype scene={scene} />}
        {surface === "agent-workspace" && <AgentWorkspaceConceptsPrototype scene={scene} />}
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
  if (surface === "selection") return "index"
  if (surface === "foundation") return "default"
  if (surface === "intelligence") return "field-primary"
  if (surface === "intelligence-journey") return "field-primary"
  if (surface === "activity") return "default"
  if (surface === "navigation") return "compact"
  if (surface === "creative") return "compare"
  if (surface === "workflow-rf") return "design"
  if (surface === "workflow-gen") return "prompt"
  if (surface === "window-manager") return "docked"
  if (surface === "page-intro") return "operating"
  if (surface === "ai-workspace") return "conversation-primary"
  if (surface === "model-studio") return "standard"
  if (surface === "dashboard") return "attention-first"
  if (surface === "agent-workspace") return "roster-detail"
  if (surface === "ai") return "compact-conversation"
  if (surface === "agents") return "default"
  return "default"
}

function normalizeAi(scene: string): AiScene {
  return (AI_SCENES as string[]).includes(scene) ? (scene as AiScene) : "compact-conversation"
}
