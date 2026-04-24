import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

type OperatorWorkspaceHeaderProps = {
  title: string;
  context: string;
  environment: string;
  timestamp: string;
  status?: string | null;
};

export function OperatorWorkspaceHeader({
  title,
  context,
  environment,
  timestamp,
  status,
}: OperatorWorkspaceHeaderProps) {
  return (
    <div className="flex items-start justify-between gap-4">
      <div>
        <p className="text-xs uppercase tracking-[0.2em] text-muted-foreground">
          AI Workspace
        </p>
        <h2 className="text-lg font-semibold text-foreground">{title}</h2>
        <p className="text-sm text-muted-foreground">{context}</p>
        {status ? (
          <span className="mt-2 inline-flex rounded-full bg-muted px-2 py-0.5 text-xs text-muted-foreground">
            Session: {status}
          </span>
        ) : null}
      </div>
      <div className="text-right text-xs text-muted-foreground">
        <p>{timestamp}</p>
        <span className="mt-2 inline-flex rounded-full bg-muted px-2 py-0.5">
          Env: {environment}
        </span>
      </div>
    </div>
  );
}

type ContextSummaryStripProps = {
  summary: string;
  hasContext?: boolean;
  onClear?: () => void;
};

export function ContextSummaryStrip({ summary, hasContext = false, onClear }: ContextSummaryStripProps) {
  return (
    <div className="rounded-md border border-border bg-[hsl(var(--surface))] px-4 py-3 text-sm text-muted-foreground">
      <div className="flex items-start justify-between gap-3">
        <div>
          <span className="text-xs uppercase tracking-[0.2em] text-muted-foreground">
            Context Summary
          </span>
          <p className="mt-1 text-sm text-foreground">{summary}</p>
        </div>
        {hasContext && onClear ? (
          <Button size="sm" variant="secondary" onClick={onClear}>
            Remove context
          </Button>
        ) : null}
      </div>
    </div>
  );
}

type ReasoningBlockProps = {
  title: string;
  body: string;
};

export function ReasoningBlock({ title, body }: ReasoningBlockProps) {
  return (
    <Card className="border-border bg-background">
      <CardHeader>
        <CardTitle className="text-sm">{title}</CardTitle>
      </CardHeader>
      <CardContent className="text-sm text-muted-foreground">
        <p>{body}</p>
      </CardContent>
    </Card>
  );
}

type ResearchResultCardProps = {
  title: string;
  items: string[];
};

export function ResearchResultCard({ title, items }: ResearchResultCardProps) {
  return (
    <Card className="border-border bg-background">
      <CardHeader>
        <CardTitle className="text-sm">{title}</CardTitle>
      </CardHeader>
      <CardContent className="text-sm text-muted-foreground space-y-1">
        {items.map((item) => (
          <p key={item}>{item}</p>
        ))}
      </CardContent>
    </Card>
  );
}
