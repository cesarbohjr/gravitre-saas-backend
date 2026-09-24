"use client"

/**
 * AI-generated workflow → compact preview → React Flow / Open in Builder.
 * Harness only · one canonical schema · fixture plan, not live Meson.
 */

import { useMemo, useState } from "react"
import {
  Background,
  Controls,
  ReactFlow,
  ReactFlowProvider,
  type Edge,
  type Node,
} from "@xyflow/react"
import "@xyflow/react/dist/style.css"
import { Button } from "@/components/ui/button"
import { TYPE } from "@/lib/design-system"
import { cn } from "@/lib/utils"
import {
  canvasToSavePayload,
  type CanvasWorkflowNode,
} from "@/lib/workflows/builder-persistence"
import { HarnessSurface } from "./topology-primitives"

const GENERATED: CanvasWorkflowNode[] = [
  {
    id: "g-src",
    type: "source",
    name: "Apollo search",
    config: {},
    position: { x: 0, y: 80 },
    connections: ["g-agent"],
    state: "idle",
  },
  {
    id: "g-agent",
    type: "agent",
    name: "Research accounts",
    config: {},
    position: { x: 220, y: 80 },
    connections: ["g-conn"],
    state: "idle",
  },
  {
    id: "g-conn",
    type: "connector",
    name: "Enrich + HubSpot",
    vendor: "hubspot",
    config: { vendor: "hubspot" },
    position: { x: 440, y: 80 },
    connections: ["g-appr"],
    state: "idle",
  },
  {
    id: "g-appr",
    type: "approval",
    name: "Outreach approval",
    config: {},
    position: { x: 660, y: 80 },
    connections: [],
    state: "idle",
  },
]

export function WorkflowGenPreviewPrototype({ scene }: { scene: string }) {
  const [stage, setStage] = useState<"prompt" | "preview" | "rf">(
    scene.includes("rf") ? "rf" : scene.includes("preview") ? "preview" : "prompt",
  )
  const payload = useMemo(() => canvasToSavePayload(GENERATED), [])
  const nodes: Node[] = GENERATED.map((n) => ({
    id: n.id,
    position: n.position,
    data: { label: `${n.type}: ${n.name}` },
    style: {
      fontSize: 11,
      border: "1px solid var(--g-border-default)",
      borderRadius: 8,
      padding: 8,
      background: "var(--g-surface-1)",
      width: 140,
    },
  }))
  const edges: Edge[] = GENERATED.flatMap((n) =>
    n.connections.map((t) => ({ id: `${n.id}-${t}`, source: n.id, target: t })),
  )

  return (
    <div data-review-surface="workflow-gen" data-review-scene={scene} className="mx-auto max-w-5xl space-y-4">
      <header>
        <p className={TYPE.eyebrow}>Selection D · AI → Workflow preview · harness only</p>
        <h2 className={cn(TYPE.pageTitle, "mt-1")}>Generate → preview → Open in Builder</h2>
        <p className={cn(TYPE.pageLead, "mt-2")}>
          Same <code className="font-mono text-xs">CanvasWorkflowNode</code> /{" "}
          <code className="font-mono text-xs">canvasToSavePayload</code>. No second workflow model. Not production Meson.
        </p>
      </header>

      <div className="flex flex-wrap gap-1">
        {(
          [
            ["prompt", "1 · Intent"],
            ["preview", "2 · Compact preview"],
            ["rf", "3 · React Flow"],
          ] as const
        ).map(([id, label]) => (
          <Button key={id} size="sm" variant={stage === id ? "secondary" : "ghost"} onClick={() => setStage(id)}>
            {label}
          </Button>
        ))}
      </div>

      {stage === "prompt" && (
        <HarnessSurface className="p-5">
          <p className={TYPE.eyebrow}>Ask Gravitre (fixture)</p>
          <p className="mt-2 text-sm">
            “Create a revenue prospecting workflow that researches accounts, identifies buying signals, enriches
            contacts, prioritizes opportunities, and prepares outreach for approval.”
          </p>
          <Button className="mt-4" size="sm" onClick={() => setStage("preview")}>
            Generate plan (fixture)
          </Button>
        </HarnessSurface>
      )}

      {stage === "preview" && (
        <HarnessSurface className="p-5">
          <p className={TYPE.eyebrow}>Compact workflow preview</p>
          <ol className="mt-3 list-decimal space-y-1 pl-5 text-sm">
            {GENERATED.map((n) => (
              <li key={n.id}>
                {n.name} <span className="text-[color:var(--g-text-muted)]">({n.type})</span>
              </li>
            ))}
          </ol>
          <div className="mt-4 flex flex-wrap gap-2">
            <Button size="sm" onClick={() => setStage("rf")}>
              Open in Workflow Builder
            </Button>
            <Button size="sm" variant="secondary">
              Edit conversationally (fixture)
            </Button>
          </div>
          <pre className="mt-4 max-h-32 overflow-auto rounded border border-[color:var(--g-border-subtle)] bg-[color:var(--g-canvas)] p-2 font-mono text-[10px]">
            {JSON.stringify({ nodes: payload.nodes.length, edges: payload.edges }, null, 2)}
          </pre>
        </HarnessSurface>
      )}

      {stage === "rf" && (
        <HarnessSurface className="h-[360px] overflow-hidden p-0">
          <ReactFlowProvider>
            <ReactFlow nodes={nodes} edges={edges} fitView proOptions={{ hideAttribution: true }}>
              <Background gap={18} color="var(--g-border-subtle)" />
              <Controls />
            </ReactFlow>
          </ReactFlowProvider>
        </HarnessSurface>
      )}
    </div>
  )
}
