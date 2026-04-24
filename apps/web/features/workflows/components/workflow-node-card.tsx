import { cn } from "@/lib/utils";
import type { WorkflowNode } from "@/lib/workflows-api";

const TYPE_LABELS: Record<WorkflowNode["node_type"], string> = {
  agent: "Agent",
  task: "Task",
  connector: "Integration",
  tool: "Tool",
  source: "Source",
};

export function WorkflowNodeCard({
  node,
  selected,
  onSelect,
}: {
  node: WorkflowNode;
  selected: boolean;
  onSelect: (id: string) => void;
}) {
  const metadata = (node.metadata ?? {}) as Record<string, unknown>;
  const role = typeof metadata.role === "string" ? metadata.role : null;
  const task = typeof metadata.task === "string" ? metadata.task : null;
  const approvalGate = metadata.approval_gate === true;

  return (
    <button
      type="button"
      onClick={() => onSelect(node.id)}
      className={cn(
        "w-[220px] rounded-lg border bg-card px-3 py-3 text-left shadow-sm transition",
        selected ? "border-primary/60 ring-2 ring-primary/20" : "border-border"
      )}
    >
      <div className="flex items-center justify-between gap-2">
        <span className="text-sm font-medium text-foreground">{node.title}</span>
        <span className="rounded-full border border-border px-2 py-0.5 text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
          {TYPE_LABELS[node.node_type]}
        </span>
      </div>
      {role ? <div className="mt-2 text-xs text-muted-foreground">Role: {role}</div> : null}
      {task ? <div className="mt-1 line-clamp-2 text-xs text-muted-foreground">{task}</div> : null}
      {approvalGate ? (
        <div className="mt-2 inline-flex rounded-full bg-muted px-2 py-0.5 text-[10px] text-muted-foreground">
          Approval gate
        </div>
      ) : null}
    </button>
  );
}
