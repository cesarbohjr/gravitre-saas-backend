import { useMemo } from "react";
import type { WorkflowEdge, WorkflowNode } from "@/lib/workflows-api";
import { WorkflowNodeCard } from "@/features/workflows/components/workflow-node-card";

const NODE_WIDTH = 220;
const NODE_HEIGHT = 96;

function fallbackPosition(index: number) {
  const col = index % 3;
  const row = Math.floor(index / 3);
  return { x: 40 + col * 260, y: 40 + row * 160 };
}

export function WorkflowCanvas({
  nodes,
  edges,
  selectedNodeId,
  onSelect,
}: {
  nodes: WorkflowNode[];
  edges: WorkflowEdge[];
  selectedNodeId: string | null;
  onSelect: (id: string) => void;
}) {
  const positions = useMemo(() => {
    const map = new Map<string, { x: number; y: number }>();
    nodes.forEach((node, index) => {
      const pos = node.position && typeof node.position === "object" ? node.position : null;
      const x = typeof pos?.x === "number" ? pos.x : fallbackPosition(index).x;
      const y = typeof pos?.y === "number" ? pos.y : fallbackPosition(index).y;
      map.set(node.id, { x, y });
    });
    return map;
  }, [nodes]);

  return (
    <div className="relative h-full min-h-[560px] overflow-hidden rounded-xl border border-border bg-muted/20">
      <svg className="pointer-events-none absolute inset-0 h-full w-full">
        {edges.map((edge) => {
          const from = positions.get(edge.from_node_id);
          const to = positions.get(edge.to_node_id);
          if (!from || !to) return null;
          const x1 = from.x + NODE_WIDTH / 2;
          const y1 = from.y + NODE_HEIGHT / 2;
          const x2 = to.x + NODE_WIDTH / 2;
          const y2 = to.y + NODE_HEIGHT / 2;
          return (
            <line
              key={edge.id}
              x1={x1}
              y1={y1}
              x2={x2}
              y2={y2}
              stroke="currentColor"
              strokeWidth="1.5"
              className="text-muted-foreground/70"
            />
          );
        })}
      </svg>
      {nodes.length === 0 ? (
        <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
          No orchestration nodes yet. Add one from the toolbox.
        </div>
      ) : null}
      {nodes.map((node, index) => {
        const position = positions.get(node.id) ?? fallbackPosition(index);
        return (
          <div
            key={node.id}
            className="absolute"
            style={{ left: position.x, top: position.y }}
          >
            <WorkflowNodeCard
              node={node}
              selected={selectedNodeId === node.id}
              onSelect={onSelect}
            />
          </div>
        );
      })}
    </div>
  );
}
