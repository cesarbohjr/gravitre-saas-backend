"use client"

/**
 * Option B structural prototype — React Flow as Workflow Builder visual layer.
 * Harness only · uses CanvasWorkflowNode + canvasToSavePayload · no production cutover.
 * Design / Live / Explain / History compositions · fixture run overlays only.
 */

import { memo, useCallback, useMemo, useState } from "react"
import {
  Background,
  Controls,
  MiniMap,
  ReactFlow,
  ReactFlowProvider,
  Handle,
  Position,
  useEdgesState,
  useNodesState,
  type Edge,
  type Node,
  type NodeProps,
  type OnConnect,
  type Connection,
} from "@xyflow/react"
import "@xyflow/react/dist/style.css"
import { Button } from "@/components/ui/button"
import { TYPE } from "@/lib/design-system"
import { cn } from "@/lib/utils"
import {
  canvasToSavePayload,
  type CanvasNodeType,
  type CanvasWorkflowNode,
  type NodeState,
} from "@/lib/workflows/builder-persistence"
import { HarnessSurface } from "./topology-primitives"

type BuilderMode = "design" | "live" | "explain" | "history"
type RfBuilderNodeData = {
  canvas: CanvasWorkflowNode
  selected: boolean
}
type RfBuilderNode = Node<RfBuilderNodeData, "workflowCanvas">

const HARNESS_FIXTURE: CanvasWorkflowNode[] = [
  {
    id: "src-inbound",
    type: "source",
    name: "Inbound lead",
    description: "Webhook / CRM source",
    config: { source_id: "fixture-source" },
    position: { x: 40, y: 160 },
    connections: ["agent-qualify"],
    state: "success",
  },
  {
    id: "agent-qualify",
    type: "agent",
    name: "Qualify lead",
    description: "Score + enrich",
    config: { agent_id: "fixture-agent" },
    position: { x: 280, y: 160 },
    connections: ["decision-route"],
    state: "running",
  },
  {
    id: "decision-route",
    type: "decision",
    name: "Route",
    description: "SQL vs nurture",
    config: {},
    position: { x: 520, y: 160 },
    connections: ["conn-hubspot", "task-nurture"],
    state: "evaluating",
    decisionConfig: {
      objective: "Route by score",
      strategy: "hybrid",
      reasoning: {
        summary: "Score ≥ 70 → HubSpot create; else nurture task.",
        confidence: 0.82,
        factors: ["score", "segment"],
        chosenPath: "sql",
      },
    },
    outputPaths: [
      { id: "sql", label: "SQL", targetNodeId: "conn-hubspot" },
      { id: "nurture", label: "Nurture", targetNodeId: "task-nurture", isDefault: true },
    ],
  },
  {
    id: "conn-hubspot",
    type: "connector",
    name: "HubSpot create",
    vendor: "hubspot",
    selectedAction: "contacts.create",
    description: "Create contact",
    config: { vendor: "hubspot", selected_action: "contacts.create" },
    position: { x: 780, y: 60 },
    connections: ["approval-send"],
    state: "waiting",
  },
  {
    id: "task-nurture",
    type: "task",
    name: "Nurture sequence",
    description: "Enqueue drip",
    config: { task: "nurture" },
    position: { x: 780, y: 280 },
    connections: [],
    state: "idle",
  },
  {
    id: "approval-send",
    type: "approval",
    name: "Approve outreach",
    description: "Human gate",
    config: {},
    position: { x: 1040, y: 60 },
    connections: [],
    state: "waiting",
  },
]

const HISTORY_FIXTURE = [
  { id: "v3", label: "v3 · current draft", at: "2026-09-23T20:10:00Z", note: "Added nurture path" },
  { id: "v2", label: "v2 · last execute", at: "2026-09-22T18:02:00Z", note: "run_fixture_01 completed" },
  { id: "v1", label: "v1 · scaffold", at: "2026-09-20T14:00:00Z", note: "Source → agent only" },
]

function stateTone(state?: NodeState): string {
  switch (state) {
    case "running":
    case "evaluating":
    case "debating":
      return "border-[color:var(--g-signal)] bg-[color:var(--g-signal-soft)]"
    case "success":
    case "consensus":
      return "border-[color:var(--g-success)] bg-[color:var(--g-success-soft)]"
    case "error":
    case "escalated":
      return "border-[color:var(--g-danger)] bg-[color:var(--g-danger-soft)]"
    case "waiting":
      return "border-[color:var(--g-warning)] bg-[color:var(--g-warning-soft)]"
    default:
      return "border-[color:var(--g-border-default)] bg-[color:var(--g-surface-1)]"
  }
}

function typeLabel(t: CanvasNodeType): string {
  return t
}

function canvasToRf(nodes: CanvasWorkflowNode[]): { nodes: RfBuilderNode[]; edges: Edge[] } {
  const rfNodes: RfBuilderNode[] = nodes.map((n) => ({
    id: n.id,
    type: "workflowCanvas",
    position: { ...n.position },
    data: { canvas: n, selected: false },
  }))
  const edges: Edge[] = []
  for (const n of nodes) {
    for (const target of n.connections) {
      edges.push({
        id: `${n.id}->${target}`,
        source: n.id,
        target,
        animated: n.state === "running" || n.state === "evaluating",
        style: { stroke: "var(--g-border-strong, #64748b)" },
      })
    }
  }
  return { nodes: rfNodes, edges }
}

function rfToCanvas(nodes: RfBuilderNode[], edges: Edge[]): CanvasWorkflowNode[] {
  return nodes.map((n) => {
    const connections = edges.filter((e) => e.source === n.id).map((e) => e.target)
    return {
      ...n.data.canvas,
      position: { x: n.position.x, y: n.position.y },
      connections,
    }
  })
}

function WorkflowCanvasNodeView({ data, selected }: NodeProps<RfBuilderNode>) {
  const n = data.canvas
  return (
    <>
      <Handle type="target" position={Position.Left} className="!h-2 !w-2 !bg-[color:var(--g-brand)]" />
      <div
        className={cn(
          "w-[200px] rounded-lg border px-3 py-2 shadow-sm",
          stateTone(n.state),
          selected && "ring-2 ring-[color:var(--g-brand)]/60",
        )}
        data-testid={`rf-node-${n.id}`}
      >
        <p className="text-[10px] font-medium uppercase tracking-wide text-[color:var(--g-text-muted)]">
          {typeLabel(n.type)}
          {n.state && n.state !== "idle" ? ` · ${n.state}` : ""}
        </p>
        <p className="truncate text-sm font-medium text-[color:var(--g-text-primary)]">{n.name}</p>
        {n.description ? (
          <p className="mt-0.5 line-clamp-2 text-[11px] text-[color:var(--g-text-secondary)]">{n.description}</p>
        ) : null}
        {n.vendor ? (
          <p className="mt-1 font-mono text-[10px] text-[color:var(--g-text-muted)]">
            {n.vendor}
            {n.selectedAction ? ` · ${n.selectedAction}` : ""}
          </p>
        ) : null}
      </div>
      <Handle type="source" position={Position.Right} className="!h-2 !w-2 !bg-[color:var(--g-brand)]" />
    </>
  )
}

const nodeTypes = { workflowCanvas: memo(WorkflowCanvasNodeView) }

function BuilderCanvasInner({
  mode,
  selectedId,
  onSelect,
}: {
  mode: BuilderMode
  selectedId: string | null
  onSelect: (id: string | null) => void
}) {
  const initial = useMemo(() => canvasToRf(HARNESS_FIXTURE), [])
  const [nodes, , onNodesChange] = useNodesState(initial.nodes)
  const [edges, setEdges, onEdgesChange] = useEdgesState(initial.edges)

  const onConnect: OnConnect = useCallback(
    (connection: Connection) => {
      if (!connection.source || !connection.target) return
      setEdges((eds) => [
        ...eds,
        {
          id: `${connection.source}->${connection.target}`,
          source: connection.source,
          target: connection.target,
        },
      ])
    },
    [setEdges],
  )

  const canvasNodes = useMemo(() => rfToCanvas(nodes, edges), [nodes, edges])
  const savePayload = useMemo(() => canvasToSavePayload(canvasNodes), [canvasNodes])
  const selected = canvasNodes.find((n) => n.id === selectedId) ?? null

  return (
    <div className="grid gap-4 lg:grid-cols-[1fr_280px]">
      <HarnessSurface className="relative h-[420px] overflow-hidden p-0">
        <div className="absolute left-3 top-3 z-10 rounded-md border border-[color:var(--g-border-default)] bg-[color:var(--g-canvas)]/95 px-2 py-1 text-[10px] uppercase tracking-wide text-[color:var(--g-text-muted)]">
          Prototype · not production builder · mode={mode}
        </div>
        <ReactFlow
          nodes={nodes.map((n) => ({
            ...n,
            data: { ...n.data, selected: n.id === selectedId },
            selected: n.id === selectedId,
          }))}
          edges={edges}
          onNodesChange={mode === "design" ? onNodesChange : undefined}
          onEdgesChange={mode === "design" ? onEdgesChange : undefined}
          onConnect={mode === "design" ? onConnect : undefined}
          nodeTypes={nodeTypes}
          fitView
          proOptions={{ hideAttribution: true }}
          nodesDraggable={mode === "design"}
          nodesConnectable={mode === "design"}
          elementsSelectable
          onSelectionChange={({ nodes: sel }) => onSelect(sel[0]?.id ?? null)}
          className="bg-[color:var(--g-canvas)]"
        >
          <Background gap={18} color="var(--g-border-subtle)" />
          <Controls showInteractive={mode === "design"} />
          <MiniMap pannable zoomable className="!bg-[color:var(--g-surface-1)]" />
        </ReactFlow>
      </HarnessSurface>

      <div className="space-y-3">
        <HarnessSurface className="p-3">
          <p className={TYPE.eyebrow}>Inspector</p>
          {selected ? (
            <div className="mt-2 space-y-1 text-sm">
              <p className="font-medium">{selected.name}</p>
              <p className="text-[color:var(--g-text-muted)]">
                {selected.type} · {selected.id}
              </p>
              {mode === "explain" && selected.decisionConfig?.reasoning ? (
                <p className="mt-2 text-xs text-[color:var(--g-text-secondary)]">
                  {selected.decisionConfig.reasoning.summary} (
                  {Math.round(selected.decisionConfig.reasoning.confidence * 100)}%)
                </p>
              ) : null}
              {mode === "live" && selected.state ? (
                <p className="mt-2 text-xs">Live overlay from fixture NodeState: {selected.state}</p>
              ) : null}
              {selected.stepError ? (
                <p className="text-xs text-[color:var(--g-danger)]">{selected.stepError}</p>
              ) : null}
            </div>
          ) : (
            <p className={cn(TYPE.meta, "mt-2")}>Select a node</p>
          )}
        </HarnessSurface>

        <HarnessSurface className="p-3">
          <p className={TYPE.eyebrow}>Persistence evidence</p>
          <p className={cn(TYPE.meta, "mt-2")}>
            Round-trip via <code className="font-mono text-[10px]">canvasToSavePayload</code> — same PUT shape as
            production builder.
          </p>
          <pre className="mt-2 max-h-40 overflow-auto rounded border border-[color:var(--g-border-subtle)] bg-[color:var(--g-canvas)] p-2 font-mono text-[10px] text-[color:var(--g-text-secondary)]">
            {JSON.stringify(
              {
                nodeCount: savePayload.nodes.length,
                edgeCount: savePayload.edges.length,
                edges: savePayload.edges.slice(0, 6),
                sampleNode: savePayload.nodes[0]
                  ? {
                      id: savePayload.nodes[0].id,
                      type: savePayload.nodes[0].type,
                      position: savePayload.nodes[0].position,
                    }
                  : null,
              },
              null,
              2,
            )}
          </pre>
        </HarnessSurface>

        {mode === "history" ? (
          <HarnessSurface className="p-3">
            <p className={TYPE.eyebrow}>History composition</p>
            <ul className="mt-2 space-y-2 text-xs">
              {HISTORY_FIXTURE.map((h) => (
                <li key={h.id} className="border-b border-[color:var(--g-border-subtle)] pb-2">
                  <p className="font-medium">{h.label}</p>
                  <p className="text-[color:var(--g-text-muted)]">{h.at}</p>
                  <p>{h.note}</p>
                </li>
              ))}
            </ul>
            <p className={cn(TYPE.meta, "mt-2")}>
              UI shell only — version restore requires functional workflow history contract (not mocked as live).
            </p>
          </HarnessSurface>
        ) : null}
      </div>
    </div>
  )
}

export function WorkflowBuilderRfPrototype({ scene }: { scene: string }) {
  const mode: BuilderMode =
    scene.includes("live")
      ? "live"
      : scene.includes("explain")
        ? "explain"
        : scene.includes("history")
          ? "history"
          : "design"
  const [selectedId, setSelectedId] = useState<string | null>("decision-route")

  return (
    <div data-review-surface="workflow-rf" data-review-scene={scene} className="mx-auto max-w-6xl space-y-4">
      <header>
        <p className={TYPE.eyebrow}>3.0 Plus · Option B prototype · harness only</p>
        <h2 className={cn(TYPE.pageTitle, "mt-1")}>React Flow Workflow Builder (visual layer)</h2>
        <p className={cn(TYPE.pageLead, "mt-2")}>
          Maps fixture <code className="font-mono text-xs">CanvasWorkflowNode[]</code> ↔ @xyflow. Does not call
          getBuilder/saveBuilder. Does not replace <code className="font-mono text-xs">app/workflows/[id]/builder</code>.
        </p>
      </header>

      <div className="flex flex-wrap gap-2">
        {(["design", "live", "explain", "history"] as const).map((m) => (
          <Button key={m} size="sm" variant={mode === m ? "secondary" : "ghost"} asChild>
            <a href={`/dev/ai-workspace-preview?s=workflow-rf&scene=${m}`}>{m}</a>
          </Button>
        ))}
      </div>

      <ReactFlowProvider>
        <BuilderCanvasInner mode={mode} selectedId={selectedId} onSelect={setSelectedId} />
      </ReactFlowProvider>

      <HarnessSurface className="p-4">
        <p className={TYPE.eyebrow}>Preservation / regression ledger</p>
        <ul className={cn(TYPE.bodyMuted, "mt-2 list-disc space-y-1 pl-5 text-sm")}>
          <li>Preserved in prototype: node types, positions, connections→edges, inspector, Design pan/zoom/minimap</li>
          <li>Preserved via shared lib (not rewritten): canvasToSavePayload edge shape {"{ fromNodeId, toNodeId }"}</li>
          <li>Composition only: Live overlays use fixture NodeState — no fake execute</li>
          <li>Composition only: Explain uses decisionConfig.reasoning when present</li>
          <li>Composition only: History list — no restore API wired</li>
          <li>Not in prototype: Meson apply, dry-run drawer, pause/cancel, decision multi-handle dimming, council debate UI</li>
          <li>Would need functional work for production: version history API, richer Live SSE step map, a11y labels on custom nodes</li>
        </ul>
      </HarnessSurface>
    </div>
  )
}
