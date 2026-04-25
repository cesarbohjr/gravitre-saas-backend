import Link from "next/link";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { ContextPack, GuardrailSummary } from "@/features/operator/types/operator";
import { OperatorEmptyState, OperatorErrorState, OperatorLoadingState } from "./operator-states";

type ContextPanelProps = {
  packs: ContextPack[];
  guardrails: GuardrailSummary | null;
  activePack?: { type: ContextPack["type"]; id: string } | null;
  onSelectPack?: (pack: { type: ContextPack["type"]; id: string } | null) => void;
  isLoading?: boolean;
  error?: string | null;
};

export function ContextPanel({
  packs,
  guardrails,
  activePack,
  onSelectPack,
  isLoading = false,
  error,
}: ContextPanelProps) {
  return (
    <div className="space-y-4">
      <Card className="border-border bg-[hsl(var(--surface))]">
        <CardHeader>
          <CardTitle className="text-lg">Context Packs</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          {isLoading ? (
            <OperatorLoadingState message="Loading context packs..." />
          ) : error ? (
            <OperatorErrorState message={error} />
          ) : packs.length === 0 ? (
            <OperatorEmptyState message="No context packs available." />
          ) : (
            packs.map((pack) => (
              <ContextPackCard
                key={`${pack.type}-${pack.id ?? "empty"}`}
                pack={pack}
                active={Boolean(activePack && pack.id && activePack.id === pack.id)}
                onSelect={onSelectPack}
              />
            ))
          )}
        </CardContent>
      </Card>

      <Card className="border-border bg-[hsl(var(--surface))]">
        <CardHeader>
          <CardTitle className="text-lg">Guardrails</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3 text-sm text-muted-foreground">
          <div>
            <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground">
              Environment
            </p>
            <p className="mt-1 text-sm text-foreground">
              {guardrails?.environment ?? "—"}
            </p>
          </div>
          <div>
            <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground">
              Approval requirements
            </p>
            <div className="mt-2 flex flex-wrap gap-2">
              {(guardrails?.approval_requirements ?? ["No guardrails loaded."]).map(
                (item) => (
                <GuardrailBadge key={item} label={item} />
              ))}
            </div>
          </div>
          <div>
            <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground">
              Admin permissions
            </p>
            <div className="mt-2 flex flex-wrap gap-2">
              {(guardrails?.admin_restrictions ?? ["Admin restrictions pending."]).map(
                (item) => (
                <GuardrailBadge key={item} label={item} />
              ))}
            </div>
          </div>
          <div>
            <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground">
              Execution restrictions
            </p>
            <div className="mt-2 flex flex-wrap gap-2">
              {(guardrails?.execution_restrictions ?? ["Confirmation required."]).map(
                (item) => (
                <GuardrailBadge key={item} label={item} />
              ))}
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

type ContextPackCardProps = {
  pack: ContextPack;
  active?: boolean;
  onSelect?: (pack: { type: ContextPack["type"]; id: string } | null) => void;
};

export function ContextPackCard({ pack, active = false, onSelect }: ContextPackCardProps) {
  const isSelectable = Boolean(pack.id);
  return (
    <Card className={active ? "border-primary/40 bg-muted" : "border-border bg-background"}>
      <CardContent className="space-y-2 p-4">
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="text-sm font-medium text-foreground">{pack.title}</p>
            <p className="text-xs text-muted-foreground">{pack.summary}</p>
          </div>
          <span className="rounded-full bg-muted px-2 py-0.5 text-xs text-muted-foreground">
            {pack.status}
          </span>
        </div>
        <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
          <span className="rounded-full bg-muted px-2 py-0.5">
            Env: {pack.environment}
          </span>
          <Link href={pack.href} className="text-primary hover:underline">
            {pack.href}
          </Link>
          <button
            type="button"
            onClick={() =>
              isSelectable && pack.id
                ? onSelect?.({ type: pack.type, id: pack.id })
                : onSelect?.(null)
            }
            disabled={!isSelectable}
            className="rounded-full border border-border bg-background px-2 py-0.5 text-xs text-muted-foreground disabled:opacity-60"
          >
            {active ? "Active" : "Set active"}
          </button>
        </div>
      </CardContent>
    </Card>
  );
}

type GuardrailBadgeProps = {
  label: string;
};

export function GuardrailBadge({ label }: GuardrailBadgeProps) {
  return (
    <span className="rounded-full bg-muted px-2 py-1 text-xs text-muted-foreground">
      {label}
    </span>
  );
}
