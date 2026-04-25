import type { IntegrationItem } from "@/lib/integrations-api";
import type { OperatorSummary } from "@/lib/operators-api";
import type { RagSource } from "@/lib/rag-api";
import { Button } from "@/components/ui/button";

type ToolOption = { id: string; label: string };

const TOOL_OPTIONS: ToolOption[] = [
  { id: "rag_retrieve", label: "RAG Retrieve" },
  { id: "http_request", label: "HTTP Request" },
  { id: "slack_post_message", label: "Slack Action" },
  { id: "email_send", label: "Email Action" },
];

export function WorkflowToolbox({
  operators,
  integrations,
  sources,
  canManage,
  onAddNode,
}: {
  operators: OperatorSummary[];
  integrations: IntegrationItem[];
  sources: RagSource[];
  canManage: boolean;
  onAddNode: (payload: {
    node_type: "agent" | "task" | "connector" | "tool" | "source";
    title: string;
    operator_id?: string | null;
    connector_id?: string | null;
    source_id?: string | null;
    tool_type?: string | null;
  }) => void;
}) {
  return (
    <div className="flex h-full flex-col gap-4">
      <div>
        <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground">Quick add</p>
        <div className="mt-2 grid gap-2">
          <Button
            size="sm"
            variant="secondary"
            disabled={!canManage}
            onClick={() => onAddNode({ node_type: "task", title: "New task" })}
          >
            Add task node
          </Button>
          <Button
            size="sm"
            variant="secondary"
            disabled={!canManage}
            onClick={() => onAddNode({ node_type: "agent", title: "Agent node" })}
          >
            Add agent node
          </Button>
        </div>
      </div>

      <div>
        <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground">Agents</p>
        <div className="mt-2 grid gap-2">
          {operators.length === 0 ? (
            <p className="text-xs text-muted-foreground">No agents available.</p>
          ) : (
            operators.map((op) => (
              <Button
                key={op.id}
                size="sm"
                variant="outline"
                disabled={!canManage}
                onClick={() => onAddNode({ node_type: "agent", title: op.name, operator_id: op.id })}
              >
                {op.name}
              </Button>
            ))
          )}
        </div>
      </div>

      <div>
        <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground">Integrations</p>
        <div className="mt-2 grid gap-2">
          {integrations.length === 0 ? (
            <p className="text-xs text-muted-foreground">No integrations available.</p>
          ) : (
            integrations.map((integration) => (
              <Button
                key={integration.id}
                size="sm"
                variant="outline"
                disabled={!canManage}
                onClick={() =>
                  onAddNode({
                    node_type: "connector",
                    title: integration.type.toUpperCase(),
                    connector_id: integration.id,
                  })
                }
              >
                {integration.type.toUpperCase()}
              </Button>
            ))
          )}
        </div>
      </div>

      <div>
        <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground">Sources</p>
        <div className="mt-2 grid gap-2">
          {sources.length === 0 ? (
            <p className="text-xs text-muted-foreground">No sources available.</p>
          ) : (
            sources.map((source) => (
              <Button
                key={source.id}
                size="sm"
                variant="outline"
                disabled={!canManage}
                onClick={() =>
                  onAddNode({
                    node_type: "source",
                    title: source.title,
                    source_id: source.id,
                  })
                }
              >
                {source.title}
              </Button>
            ))
          )}
        </div>
      </div>

      <div>
        <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground">Tools</p>
        <div className="mt-2 grid gap-2">
          {TOOL_OPTIONS.map((tool) => (
            <Button
              key={tool.id}
              size="sm"
              variant="outline"
              disabled={!canManage}
              onClick={() =>
                onAddNode({
                  node_type: "tool",
                  title: tool.label,
                  tool_type: tool.id,
                })
              }
            >
              {tool.label}
            </Button>
          ))}
        </div>
      </div>

      {!canManage ? (
        <p className="text-xs text-muted-foreground">Read-only. Admin access required to edit.</p>
      ) : null}
    </div>
  );
}
