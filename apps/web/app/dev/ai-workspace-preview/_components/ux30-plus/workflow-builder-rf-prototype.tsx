"use client"

/**
 * Option B structural prototype — React Flow as Workflow Builder visual layer.
 * Harness only · uses CanvasWorkflowNode + canvasToSavePayload · no production cutover.
 * Design / Live / Explain / History compositions · fixture run overlays only.
 */

import { useCallback, useEffect, useMemo, useState } from "react"
import {
  Background,
  Controls,
  MiniMap,
  ReactFlow,
  ReactFlowProvider,
  useEdgesState,
  useNodesState,
  type Edge,
  type Node,
  type OnConnect,
  type Connection,
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

type BuilderMode = "design" | "live" | "explain" | "history" | "ai-preview"
type RfBuilderNodeData = {
  label?: string
  canvas: CanvasWorkflowNode
  selected: boolean
}

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

function canvasToRf(nodes: CanvasWorkflowNode[]): { nodes: Node[]; edges: Edge[] } {
  const rfNodes: Node[] = nodes.map((n) => ({
    id: n.id,
    type: "default",
    position: { ...n.position },
    data: {
      label: `${n.name}\n(${n.type}${n.state && n.state !== "idle" ? ` · ${n.state}` : ""})`,
      canvas: n,
      selected: false,
    },
    style: {
      width: 200,
      border: "1px solid var(--g-border-default)",
      borderRadius: 8,
      fontSize: 12,
      background: "var(--g-surface-1)",
    },
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

function rfToCanvas(nodes: Node[], edges: Edge[]): CanvasWorkflowNode[] {
  return nodes.map((n) => {
    const connections = edges.filter((e) => e.source === n.id).map((e) => e.target)
    const canvas = (n.data as RfBuilderNodeData).canvas
    return {
      ...canvas,
      position: { x: n.position.x, y: n.position.y },
      connections,
    }
  })
}

function BuilderCanvasInner({
  mode,
  selectedId,
  onSelect,
  selectedEdgeId,
  onSelectEdge,
}: {
  mode: BuilderMode
  selectedId: string | null
  onSelect: (id: string | null) => void
  selectedEdgeId: string | null
  onSelectEdge: (id: string | null) => void
}) {
  const [mounted, setMounted] = useState(false)
  useEffect(() => {
    setMounted(true)
  }, [])

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

  const canvasNodes = useMemo(() => {
    // Prefer live RF graph; fall back to fixture so inspector/save proof always works.
    if (nodes.length > 0) return rfToCanvas(nodes, edges)
    return HARNESS_FIXTURE
  }, [nodes, edges])
  const savePayload = useMemo(() => canvasToSavePayload(canvasNodes), [canvasNodes])
  const selected = canvasNodes.find((n) => n.id === selectedId) ?? null
  const selectedEdge = edges.find((e) => e.id === selectedEdgeId) ?? null
  const editable = mode === "design" || mode === "ai-preview"

  return (
    <div className="space-y-3">
      <HarnessSurface className="p-3">
        <p className={TYPE.eyebrow}>Representative workflow · fixture · click to inspect</p>
        <div className="mt-3 flex flex-wrap items-center gap-2">
          {HARNESS_FIXTURE.map((n, i) => (
            <div key={n.id} className="flex items-center gap-2">
              {i > 0 ? <span className="text-[color:var(--g-text-muted)]">→</span> : null}
              <button
                type="button"
                data-testid={`rf-node-${n.id}`}
                onClick={() => onSelect(n.id)}
                className={cn(
                  "rounded-lg border px-3 py-2 text-left text-sm",
                  selectedId === n.id
                    ? "border-[color:var(--g-brand)] bg-[color:var(--g-brand-soft)]"
                    : "border-[color:var(--g-border-subtle)] bg-[color:var(--g-surface-1)]",
                )}
              >
                <span className="block text-[10px] uppercase text-[color:var(--g-text-muted)]">
                  {n.type}
                  {n.state && n.state !== "idle" ? ` · ${n.state}` : ""}
                </span>
                <span className="font-medium">{n.name}</span>
              </button>
            </div>
          ))}
        </div>
        <p className={cn(TYPE.meta, "mt-2")}>
          Same CanvasWorkflowNode fixture as RF layer · branches at Route → HubSpot / Nurture
        </p>
      </HarnessSurface>

      <div className="grid gap-4 lg:grid-cols-[1fr_280px]">
        <HarnessSurface className="relative h-[420px] overflow-hidden p-0">
          <div className="absolute left-3 top-3 z-10 rounded-md border border-[color:var(--g-border-default)] bg-[color:var(--g-canvas)]/95 px-2 py-1 text-[10px] uppercase tracking-wide text-[color:var(--g-text-muted)]">
            @xyflow visual layer · mode={mode} · client-mounted={mounted ? "yes" : "no"}
          </div>
          {mounted ? (
            <div className="h-full w-full">
              <ReactFlow
                nodes={nodes.map((n) => ({
                  ...n,
                  selected: n.id === selectedId,
                }))}
                edges={edges.map((e) => ({
                  ...e,
                  selected: e.id === selectedEdgeId,
                  style: {
                    ...e.style,
                    stroke: e.id === selectedEdgeId ? "var(--g-brand)" : "var(--g-border-strong, #64748b)",
                    strokeWidth: e.id === selectedEdgeId ? 2.5 : 1.5,
                  },
                }))}
                onNodesChange={editable ? onNodesChange : onNodesChange}
                onEdgesChange={editable ? onEdgesChange : undefined}
                onConnect={editable ? onConnect : undefined}
                fitView
                fitViewOptions={{ padding: 0.25 }}
                minZoom={0.2}
                maxZoom={1.75}
                proOptions={{ hideAttribution: true }}
                nodesDraggable={editable}
                nodesConnectable={editable}
                elementsSelectable
                onNodeClick={(_, node) => onSelect(node.id)}
                onEdgeClick={(_, edge) => onSelectEdge(edge.id)}
                className="h-full w-full bg-[color:var(--g-canvas)]"
                style={{ width: "100%", height: "100%" }}
              >
                <Background gap={18} color="var(--g-border-subtle)" />
                <Controls showInteractive={editable} />
                <MiniMap pannable zoomable className="!bg-[color:var(--g-surface-1)]" />
              </ReactFlow>
            </div>
          ) : (
            <div className="flex h-full items-center justify-center text-sm text-[color:var(--g-text-muted)]">
              Mounting React Flow…
            </div>
          )}
        </HarnessSurface>

        <div className="space-y-3">
          {mode === "ai-preview" && (
            <HarnessSurface className="p-3">
              <p className={TYPE.eyebrow}>AI-generated (fixture)</p>
              <p className="mt-1 text-xs">Plan applied to canonical nodes · Open full builder = production route later</p>
              <Button size="sm" className="mt-2" variant="secondary" asChild>
                <a href="/dev/ai-workspace-preview?s=workflow-gen&scene=preview">Open gen composition</a>
              </Button>
            </HarnessSurface>
          )}
          <HarnessSurface className="p-3">
            <p className={TYPE.eyebrow}>Node inspector</p>
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
              </div>
            ) : (
              <p className={cn(TYPE.meta, "mt-2")}>Select a node</p>
            )}
          </HarnessSurface>

          <HarnessSurface className="p-3">
            <p className={TYPE.eyebrow}>Edge inspector</p>
            {selectedEdge ? (
              <div className="mt-2 space-y-1 text-xs">
                <p className="font-mono">{selectedEdge.id}</p>
                <p>
                  {selectedEdge.source} → {selectedEdge.target}
                </p>
                <p className="text-[color:var(--g-text-muted)]">Maps to connections[] / fromNodeId·toNodeId</p>
              </div>
            ) : (
              <p className={cn(TYPE.meta, "mt-2")}>Select an edge · or inspect via node connections</p>
            )}
          </HarnessSurface>

          <HarnessSurface className="p-3">
            <p className={TYPE.eyebrow}>Save/load mapping evidence</p>
            <pre className="mt-2 max-h-36 overflow-auto rounded border border-[color:var(--g-border-subtle)] bg-[color:var(--g-canvas)] p-2 font-mono text-[10px] text-[color:var(--g-text-secondary)]">
              {JSON.stringify(
                {
                  nodeCount: savePayload.nodes.length,
                  edgeCount: savePayload.edges.length,
                  edges: savePayload.edges.slice(0, 8),
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
              <p className={cn(TYPE.meta, "mt-2")}>UI shell only — version restore API not wired (functional gap).</p>
            </HarnessSurface>
          ) : null}
        </div>
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
          : scene.includes("ai-preview") || scene.includes("ai")
            ? "ai-preview"
            : "design"
  const [selectedId, setSelectedId] = useState<string | null>("decision-route")
  const [selectedEdgeId, setSelectedEdgeId] = useState<string | null>(null)

  return (
    <div data-review-surface="workflow-rf" data-review-scene={scene} className="mx-auto max-w-6xl space-y-4">
      <header>
        <p className={TYPE.eyebrow}>Selection D · Option B prototype · harness only</p>
        <h2 className={cn(TYPE.pageTitle, "mt-1")}>React Flow Workflow Builder (visual layer)</h2>
        <p className={cn(TYPE.pageLead, "mt-2")}>
          Demonstrated vs conceptual distinguished below. Production builder untouched. Gaps: Meson apply, decision
          multi-handles, council UI, version restore API, live runsApi overlays.
        </p>
      </header>

      <div className="flex flex-wrap gap-2">
        {(["design", "live", "explain", "history", "ai-preview"] as const).map((m) => (
          <Button key={m} size="sm" variant={mode === m ? "secondary" : "ghost"} asChild>
            <a href={`/dev/ai-workspace-preview?s=workflow-rf&scene=${m}`}>{m}</a>
          </Button>
        ))}
      </div>

      <ReactFlowProvider>
        <BuilderCanvasInner
          mode={mode}
          selectedId={selectedId}
          onSelect={setSelectedId}
          selectedEdgeId={selectedEdgeId}
          onSelectEdge={setSelectedEdgeId}
        />
      </ReactFlowProvider>

      <HarnessSurface className="p-4">
        <p className={TYPE.eyebrow}>Demonstrated vs conceptual</p>
        <ul className={cn(TYPE.bodyMuted, "mt-2 list-disc space-y-1 pl-5 text-sm")}>
          <li>
            <strong>Demonstrated:</strong> RF canvas, Design edit/connect, node+edge inspect, canvasToSavePayload,
            Live/Explain/History compositions, AI-preview fixture graph
          </li>
          <li>
            <strong>Conceptual / not wired:</strong> getBuilder/saveBuilder HTTP, Meson apply, decision multi-handles,
            council debate, version restore, runsApi live poll
          </li>
        </ul>
      </HarnessSurface>
    </div>
  )
}
