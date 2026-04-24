import type { OperatorSummary } from "@/lib/operators-api";

type OperatorSelectorProps = {
  operators: OperatorSummary[];
  activeOperatorId?: string | null;
  onSelect?: (id: string) => void;
  disabled?: boolean;
};

export function OperatorSelector({
  operators,
  activeOperatorId,
  onSelect,
  disabled = false,
}: OperatorSelectorProps) {
  return (
    <div className="space-y-1">
      <label className="text-xs uppercase tracking-[0.2em] text-muted-foreground">
        Operator
      </label>
      <select
        className="w-full min-w-[220px] rounded-md border border-border bg-background px-3 py-2 text-sm"
        value={activeOperatorId ?? ""}
        onChange={(event) => onSelect?.(event.target.value)}
        disabled={disabled || operators.length === 0}
      >
        {operators.length === 0 ? (
          <option value="">No operators available</option>
        ) : (
          operators.map((op) => (
            <option key={op.id} value={op.id}>
              {op.name} · {op.status}
            </option>
          ))
        )}
      </select>
    </div>
  );
}
