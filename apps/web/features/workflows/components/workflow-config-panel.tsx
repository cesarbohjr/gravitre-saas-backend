import { useEffect, useMemo, useState } from "react";
import { Button } from "@/components/ui/button";
import type { IntegrationItem } from "@/lib/integrations-api";
import type { OperatorSummary } from "@/lib/operators-api";
import type { RagSource } from "@/lib/rag-api";
import type { WorkflowEdge, WorkflowNode } from "@/lib/workflows-api";

function toNumber(value: string, fallback: number) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

export function WorkflowConfigPanel({
  node,
  nodes,
  edges,
  operators,
  integrations,
  sources,
  canManage,
  onSaveNode,
  onDeleteNode,
  onCreateEdge,
  onDeleteEdge,
}: {
  node: WorkflowNode | null;
  nodes: WorkflowNode[];
  edges: WorkflowEdge[];
  operators: OperatorSummary[];
  integrations: IntegrationItem[];
  sources: RagSource[];
  canManage: boolean;
  onSaveNode: (payload: Partial<WorkflowNode>) => Promise<void>;
  onDeleteNode: (nodeId: string) => Promise<void>;
  onCreateEdge: (payload: { to_node_id: string; edge_type: WorkflowEdge["edge_type"] }) => Promise<void>;
  onDeleteEdge: (edgeId: string) => Promise<void>;
}) {
  const [draft, setDraft] = useState<WorkflowNode | null>(node);
  const [saving, setSaving] = useState(false);
  const [edgeTarget, setEdgeTarget] = useState("");
  const [edgeType, setEdgeType] = useState<WorkflowEdge["edge_type"]>("sequence");

  useEffect(() => {
    setDraft(node);
    setEdgeTarget("");
    setEdgeType("sequence");
  }, [node]);

  const metadata = useMemo(() => {
    return ((draft?.metadata ?? {}) as Record<string, unknown>) || {};
  }, [draft]);

  const outgoingEdges = useMemo(() => {
    if (!draft) return [];
    return edges.filter((edge) => edge.from_node_id === draft.id);
  }, [draft, edges]);

  if (!draft) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
        Select a node to configure.
      </div>
    );
  }

  const position = (draft.position ?? {}) as { x?: number; y?: number };
  const role = typeof metadata.role === "string" ? metadata.role : "";
  const task = typeof metadata.task === "string" ? metadata.task : "";
  const approvalGate = metadata.approval_gate === true;
  const nextAgentId = typeof metadata.next_agent_id === "string" ? metadata.next_agent_id : "";

  async function handleSave() {
    if (!canManage || !draft) return;
    setSaving(true);
    try {
      const nextMetadata = {
        ...metadata,
        role: role || undefined,
        task: task || undefined,
        approval_gate: approvalGate,
        next_agent_id: nextAgentId || undefined,
      };
      const positionPayload =
        draft.position && typeof position.x === "number" && typeof position.y === "number"
          ? {
              x: toNumber(String(position.x ?? 0), 0),
              y: toNumber(String(position.y ?? 0), 0),
            }
          : undefined;
      await onSaveNode({
        title: draft.title,
        instruction: draft.instruction ?? null,
        operator_id: draft.operator_id ?? null,
        connector_id: draft.connector_id ?? null,
        source_id: draft.source_id ?? null,
        tool_type: draft.tool_type ?? null,
        tool_config: draft.tool_config ?? null,
        position: positionPayload,
        metadata: nextMetadata,
      });
    } finally {
      setSaving(false);
    }
  }

  async function handleAddEdge() {
    if (!draft || !edgeTarget || !canManage) return;
    await onCreateEdge({ to_node_id: edgeTarget, edge_type: edgeType });
    setEdgeTarget("");
  }

  return (
    <div className="flex h-full flex-col gap-4 overflow-auto">
      <div>
        <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground">Node settings</p>
        <div className="mt-3 grid gap-3">
          <div className="grid gap-2">
            <label className="text-xs text-muted-foreground">Title</label>
            <input
              className="h-9 rounded-md border border-border bg-background px-3 text-sm"
              value={draft.title}
              onChange={(event) => setDraft({ ...draft, title: event.target.value })}
              disabled={!canManage}
            />
          </div>
          <div className="grid gap-2">
            <label className="text-xs text-muted-foreground">Instruction</label>
            <textarea
              className="rounded-md border border-border bg-background px-3 py-2 text-sm"
              rows={3}
              value={draft.instruction ?? ""}
              onChange={(event) => setDraft({ ...draft, instruction: event.target.value })}
              disabled={!canManage}
            />
          </div>

          <div className="grid gap-2">
            <label className="text-xs text-muted-foreground">Role</label>
            <input
              className="h-9 rounded-md border border-border bg-background px-3 text-sm"
              value={role}
              onChange={(event) =>
                setDraft({
                  ...draft,
                  metadata: { ...metadata, role: event.target.value },
                })
              }
              disabled={!canManage}
            />
          </div>

          <div className="grid gap-2">
            <label className="text-xs text-muted-foreground">Task</label>
            <textarea
              className="rounded-md border border-border bg-background px-3 py-2 text-sm"
              rows={3}
              value={task}
              onChange={(event) =>
                setDraft({
                  ...draft,
                  metadata: { ...metadata, task: event.target.value },
                })
              }
              disabled={!canManage}
            />
          </div>

          <label className="flex items-center gap-2 text-xs text-muted-foreground">
            <input
              type="checkbox"
              checked={approvalGate}
              onChange={(event) =>
                setDraft({
                  ...draft,
                  metadata: { ...metadata, approval_gate: event.target.checked },
                })
              }
              disabled={!canManage}
            />
            Approval gate required
          </label>

          <div className="grid gap-2">
            <label className="text-xs text-muted-foreground">Next agent</label>
            <select
              className="h-9 rounded-md border border-border bg-background px-3 text-sm"
              value={nextAgentId}
              onChange={(event) =>
                setDraft({
                  ...draft,
                  metadata: { ...metadata, next_agent_id: event.target.value },
                })
              }
              disabled={!canManage}
            >
              <option value="">None</option>
              {operators.map((op) => (
                <option key={op.id} value={op.id}>
                  {op.name}
                </option>
              ))}
            </select>
          </div>
        </div>
      </div>

      <div>
        <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground">Bindings</p>
        <div className="mt-3 grid gap-3">
          {draft.node_type === "agent" ? (
            <div className="grid gap-2">
              <label className="text-xs text-muted-foreground">Operator</label>
              <select
                className="h-9 rounded-md border border-border bg-background px-3 text-sm"
                value={draft.operator_id ?? ""}
                onChange={(event) => setDraft({ ...draft, operator_id: event.target.value })}
                disabled={!canManage}
              >
                <option value="">Select operator</option>
                {operators.map((op) => (
                  <option key={op.id} value={op.id}>
                    {op.name}
                  </option>
                ))}
              </select>
            </div>
          ) : null}
          {draft.node_type === "connector" ? (
            <div className="grid gap-2">
              <label className="text-xs text-muted-foreground">Integration</label>
              <select
                className="h-9 rounded-md border border-border bg-background px-3 text-sm"
                value={draft.connector_id ?? ""}
                onChange={(event) => setDraft({ ...draft, connector_id: event.target.value })}
                disabled={!canManage}
              >
                <option value="">Select integration</option>
                {integrations.map((integration) => (
                  <option key={integration.id} value={integration.id}>
                    {integration.type.toUpperCase()}
                  </option>
                ))}
              </select>
            </div>
          ) : null}
          {draft.node_type === "source" ? (
            <div className="grid gap-2">
              <label className="text-xs text-muted-foreground">Source</label>
              <select
                className="h-9 rounded-md border border-border bg-background px-3 text-sm"
                value={draft.source_id ?? ""}
                onChange={(event) => setDraft({ ...draft, source_id: event.target.value })}
                disabled={!canManage}
              >
                <option value="">Select source</option>
                {sources.map((source) => (
                  <option key={source.id} value={source.id}>
                    {source.title}
                  </option>
                ))}
              </select>
            </div>
          ) : null}
          {draft.node_type === "tool" ? (
            <div className="grid gap-2">
              <label className="text-xs text-muted-foreground">Tool type</label>
              <input
                className="h-9 rounded-md border border-border bg-background px-3 text-sm"
                value={draft.tool_type ?? ""}
                onChange={(event) => setDraft({ ...draft, tool_type: event.target.value })}
                disabled={!canManage}
              />
            </div>
          ) : null}
        </div>
      </div>

      <div>
        <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground">Position</p>
        <div className="mt-3 grid grid-cols-2 gap-2">
          <div className="grid gap-2">
            <label className="text-xs text-muted-foreground">X</label>
            <input
              className="h-9 rounded-md border border-border bg-background px-3 text-sm"
              value={String(position.x ?? 0)}
              onChange={(event) =>
                setDraft({
                  ...draft,
                  position: { ...position, x: toNumber(event.target.value, 0) },
                })
              }
              disabled={!canManage}
            />
          </div>
          <div className="grid gap-2">
            <label className="text-xs text-muted-foreground">Y</label>
            <input
              className="h-9 rounded-md border border-border bg-background px-3 text-sm"
              value={String(position.y ?? 0)}
              onChange={(event) =>
                setDraft({
                  ...draft,
                  position: { ...position, y: toNumber(event.target.value, 0) },
                })
              }
              disabled={!canManage}
            />
          </div>
        </div>
      </div>

      <div>
        <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground">Connections</p>
        <div className="mt-3 grid gap-3">
          <div className="grid gap-2">
            <label className="text-xs text-muted-foreground">Connect to</label>
            <select
              className="h-9 rounded-md border border-border bg-background px-3 text-sm"
              value={edgeTarget}
              onChange={(event) => setEdgeTarget(event.target.value)}
              disabled={!canManage}
            >
              <option value="">Select node</option>
              {nodes
                .filter((item) => item.id !== draft.id)
                .map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.title}
                  </option>
                ))}
            </select>
          </div>
          <div className="grid gap-2">
            <label className="text-xs text-muted-foreground">Edge type</label>
            <select
              className="h-9 rounded-md border border-border bg-background px-3 text-sm"
              value={edgeType}
              onChange={(event) => setEdgeType(event.target.value as WorkflowEdge["edge_type"])}
              disabled={!canManage}
            >
              <option value="sequence">Sequence</option>
              <option value="branch">Branch</option>
              <option value="condition">Condition</option>
            </select>
          </div>
          <Button size="sm" variant="secondary" onClick={handleAddEdge} disabled={!canManage || !edgeTarget}>
            Add edge
          </Button>
        </div>
        {outgoingEdges.length > 0 ? (
          <div className="mt-4 grid gap-2">
            {outgoingEdges.map((edge) => {
              const target = nodes.find((item) => item.id === edge.to_node_id);
              return (
                <div key={edge.id} className="flex items-center justify-between rounded-md border border-border px-3 py-2 text-xs">
                  <span className="text-muted-foreground">
                    {edge.edge_type} → {target?.title ?? "Unknown"}
                  </span>
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => onDeleteEdge(edge.id)}
                    disabled={!canManage}
                  >
                    Remove
                  </Button>
                </div>
              );
            })}
          </div>
        ) : (
          <p className="mt-3 text-xs text-muted-foreground">No outgoing edges yet.</p>
        )}
      </div>

      <div className="mt-auto grid gap-2">
        <Button size="sm" onClick={handleSave} disabled={!canManage || saving}>
          {saving ? "Saving..." : "Save node"}
        </Button>
        <Button
          size="sm"
          variant="destructive"
          onClick={() => onDeleteNode(draft.id)}
          disabled={!canManage}
        >
          Delete node
        </Button>
        {!canManage ? <p className="text-xs text-muted-foreground">Read-only. Admin access required.</p> : null}
      </div>
    </div>
  );
}
