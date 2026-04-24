"use client";

import { useMemo } from "react";
import { Button } from "@/components/ui/button";
import {
  ActionPlan,
  ActionProposalCard,
  ContextPanel,
  ContextSummaryStrip,
  OperatorExecutionHistory,
  OperatorErrorState,
  OperatorEmptyState,
  OperatorSelector,
  OperatorSessionList,
  OperatorTaskInput,
  OperatorWorkspaceHeader,
  ReasoningBlock,
  ResearchResultCard,
} from "@/features/operator/components";
import { useOperatorData } from "@/features/operator/hooks/use-operator-data";
import { getEnvironmentHeader } from "@/lib/environment";

export default function OperatorPage() {
  const environment = getEnvironmentHeader();
  const {
    operators,
    activeOperatorId,
    setActiveOperatorId,
    sessions,
    actionPlan,
    proposals,
    contextPacks,
    guardrails,
    workspace,
    executionHistory,
    sessionStatus,
    isLoading,
    isPlanning,
    isExecuting,
    error,
    activePack,
    setActivePack,
    activeSessionId,
    setActiveSessionId,
    createSession,
    createPlan,
    runAction,
  } = useOperatorData();

  const activeSession = useMemo(
    () => sessions.find((session) => session.id === activeSessionId) ?? sessions[0],
    [activeSessionId, sessions]
  );

  const sessionTitle = activeSession?.title ?? "No active session";
  const sessionContext = activeSession?.contextEntity ?? "Select or create a session.";
  const sessionEnvironment = activeSession?.environment ?? environment;
  const sessionTimestamp = activeSession?.timestamp ?? "—";
  const hasActiveOperator = Boolean(activeOperatorId);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-3xl font-semibold tracking-tight text-foreground">
            AI Operator
          </h1>
          <p className="text-sm text-muted-foreground">
            Environment: <span className="font-medium text-foreground">{environment}</span>
          </p>
        </div>
        <div className="flex flex-wrap items-end gap-4">
          <OperatorSelector
            operators={operators}
            activeOperatorId={activeOperatorId}
            onSelect={setActiveOperatorId}
            disabled={isLoading}
          />
          <Button
            size="sm"
            variant="secondary"
            onClick={() => createSession(`Session · ${new Date().toLocaleString()}`)}
            disabled={!hasActiveOperator || isLoading}
            title={!hasActiveOperator ? "Select an operator first" : undefined}
          >
            New session
          </Button>
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-[260px,1fr,320px]">
        <section className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold uppercase tracking-[0.14em] text-muted-foreground">
              Operator Sessions
            </h2>
            <Button
              size="sm"
              variant="secondary"
              onClick={() => createSession(`Session · ${new Date().toLocaleString()}`)}
              disabled={!hasActiveOperator || isLoading}
              title={!hasActiveOperator ? "Select an operator first" : undefined}
            >
              New
            </Button>
          </div>
          {error ? (
            <OperatorErrorState message={error} />
          ) : (
            <OperatorSessionList
              sessions={sessions}
              activeSessionId={activeSessionId}
              onSelectSession={setActiveSessionId}
              isLoading={isLoading}
            />
          )}
        </section>

        <section className="space-y-6">
          <div className="space-y-4 rounded-lg border border-border bg-[hsl(var(--surface))] p-5">
            <OperatorWorkspaceHeader
              title={sessionTitle}
              context={sessionContext}
              environment={sessionEnvironment}
              timestamp={sessionTimestamp}
              status={sessionStatus}
            />
            <ContextSummaryStrip
              summary={workspace.contextSummary}
              hasContext={Boolean(activePack)}
              onClear={() => setActivePack(null)}
            />
            <OperatorTaskInput
              onSubmit={createPlan}
              isLoading={isPlanning}
              disabled={!activeSessionId || !activePack?.id}
              contextLabel={
                activePack?.id
                  ? `Primary context: ${activePack.type} · ${activePack.id.slice(0, 8)}…`
                  : "Select a context pack to generate a plan."
              }
            />
            <div className="grid gap-4 md:grid-cols-2">
              <ReasoningBlock title="Reasoning" body={workspace.reasoning} />
              {workspace.researchResults.map((result) => (
                <ResearchResultCard
                  key={result.id}
                  title={result.title}
                  items={result.items}
                />
              ))}
            </div>
          </div>

          {actionPlan ? (
            <ActionPlan
              title={actionPlan.title}
              summary={actionPlan.summary}
              steps={actionPlan.steps}
            />
          ) : (
            <div className="rounded-lg border border-border bg-[hsl(var(--surface))] p-5">
              <OperatorEmptyState message="No action plan loaded yet." />
            </div>
          )}

          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold uppercase tracking-[0.14em] text-muted-foreground">
                Action Proposals
              </h3>
              <span className="text-xs text-muted-foreground">Confirm before execution</span>
            </div>
            <div className="grid gap-3 md:grid-cols-2">
              {proposals.length === 0 ? (
                <OperatorEmptyState message="No action proposals yet." />
              ) : (
                proposals.map((proposal) => (
                  <ActionProposalCard
                    key={proposal.id}
                    title={proposal.title}
                    description={proposal.description}
                    environment={proposal.environment}
                    requiresApproval={proposal.requiresApproval}
                    requiresAdmin={proposal.requiresAdmin}
                    executionState={proposal.executionState}
                    confirmationRequired={proposal.confirmationRequired}
                    ctaLabel={proposal.ctaLabel}
                    onConfirm={() => runAction(proposal.stepId)}
                    isExecuting={isExecuting}
                  />
                ))
              )}
            </div>
          </div>

          <OperatorExecutionHistory actions={executionHistory} isLoading={isLoading} />
        </section>

        <aside className="space-y-4">
          <ContextPanel
            packs={contextPacks}
            guardrails={guardrails}
            activePack={activePack}
            onSelectPack={setActivePack}
            isLoading={isLoading}
            error={error}
          />
        </aside>
      </div>
    </div>
  );
}
