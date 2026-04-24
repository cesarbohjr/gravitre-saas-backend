import type { OperatorSession } from "@/features/operator/types/operator";
import { OperatorEmptyState, OperatorLoadingState } from "./operator-states";
import { OperatorSessionItem } from "./operator-session-item";

type OperatorSessionListProps = {
  sessions: OperatorSession[];
  activeSessionId?: string;
  onSelectSession?: (id: string) => void;
  isLoading?: boolean;
};

export function OperatorSessionList({
  sessions,
  activeSessionId,
  onSelectSession,
  isLoading = false,
}: OperatorSessionListProps) {
  if (isLoading) {
    return <OperatorLoadingState message="Loading sessions..." />;
  }

  if (sessions.length === 0) {
    return <OperatorEmptyState message="No operator sessions yet." />;
  }

  return (
    <div className="space-y-2">
      {sessions.map((session) => (
        <OperatorSessionItem
          key={session.id}
          session={session}
          active={session.id === activeSessionId}
          onSelect={onSelectSession}
        />
      ))}
    </div>
  );
}
