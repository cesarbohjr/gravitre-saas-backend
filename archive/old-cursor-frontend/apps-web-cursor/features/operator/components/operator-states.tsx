import { Button } from "@/components/ui/button";

type OperatorEmptyStateProps = {
  message: string;
};

export function OperatorEmptyState({ message }: OperatorEmptyStateProps) {
  return <p className="text-sm text-muted-foreground">{message}</p>;
}

type OperatorLoadingStateProps = {
  message?: string;
};

export function OperatorLoadingState({ message = "Loading..." }: OperatorLoadingStateProps) {
  return <p className="text-sm text-muted-foreground">{message}</p>;
}

type OperatorErrorStateProps = {
  message: string;
  onRetry?: () => void;
};

export function OperatorErrorState({ message, onRetry }: OperatorErrorStateProps) {
  return (
    <div className="flex items-center justify-between gap-4">
      <p className="text-sm text-destructive">{message}</p>
      {onRetry ? (
        <Button size="sm" variant="secondary" onClick={onRetry}>
          Retry
        </Button>
      ) : null}
    </div>
  );
}
