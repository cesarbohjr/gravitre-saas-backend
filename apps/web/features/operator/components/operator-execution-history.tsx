import Link from "next/link";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { OperatorAction } from "@/lib/operators-api";

type OperatorExecutionHistoryProps = {
  actions: OperatorAction[];
  isLoading?: boolean;
};

export function OperatorExecutionHistory({
  actions,
  isLoading = false,
}: OperatorExecutionHistoryProps) {
  return (
    <Card className="border-border bg-[hsl(var(--surface))]">
      <CardHeader>
        <CardTitle className="text-lg">Execution history</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3 text-sm text-muted-foreground">
        {isLoading ? (
          <p>Loading execution history…</p>
        ) : actions.length === 0 ? (
          <p>No operator executions recorded yet.</p>
        ) : (
          <div className="space-y-2">
            {actions.map((action) => (
              <div
                key={action.id}
                className="rounded-md border border-border bg-background px-3 py-2"
              >
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="text-sm text-foreground">
                      {action.action_type} · Step {action.step_id}
                    </p>
                    <p className="text-xs text-muted-foreground">
                      {action.created_at ? new Date(action.created_at).toLocaleString() : "—"}
                    </p>
                  </div>
                  <span className="rounded-full bg-muted px-2 py-0.5 text-xs text-muted-foreground">
                    {action.status}
                  </span>
                </div>
                {action.workflow_run_id ? (
                  <Link
                    href={`/runs/${action.workflow_run_id}`}
                    className="mt-2 inline-block text-xs text-primary hover:underline"
                  >
                    View run {action.workflow_run_id.slice(0, 8)}…
                  </Link>
                ) : null}
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
