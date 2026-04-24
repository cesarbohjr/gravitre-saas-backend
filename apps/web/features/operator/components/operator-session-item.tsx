import { cn } from "@/lib/utils";
import type { OperatorSession } from "@/features/operator/types/operator";

type OperatorSessionItemProps = {
  session: OperatorSession;
  active?: boolean;
  onSelect?: (id: string) => void;
};

export function OperatorSessionItem({
  session,
  active = false,
  onSelect,
}: OperatorSessionItemProps) {
  return (
    <button
      type="button"
      onClick={() => onSelect?.(session.id)}
      className={cn(
        "w-full rounded-md border px-3 py-3 text-left transition-colors",
        active
          ? "border-primary/40 bg-muted text-foreground"
          : "border-border bg-[hsl(var(--surface))] text-muted-foreground hover:text-foreground"
      )}
    >
      <div className="flex items-center justify-between gap-3">
        <span className="text-sm font-medium text-foreground">{session.title}</span>
        <span className="text-xs text-muted-foreground">{session.timestamp}</span>
      </div>
      <p className="mt-2 text-xs text-muted-foreground">{session.contextEntity}</p>
      <div className="mt-2 flex flex-wrap items-center gap-2 text-[11px] text-muted-foreground">
        <span className="rounded-full bg-muted px-2 py-0.5">
          Env: {session.environment}
        </span>
        {session.status ? (
          <span className="rounded-full bg-muted px-2 py-0.5">
            {session.status.replaceAll("_", " ")}
          </span>
        ) : null}
        {active ? (
          <span className="rounded-full bg-muted px-2 py-0.5">Active</span>
        ) : null}
      </div>
    </button>
  );
}
