"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { fetchContextPack } from "@/features/operator/api/operator-api";
import type {
  ActionPlan,
  ContextPack,
  ContextPackType,
  GuardrailSummary,
  OperatorContextPack,
  OperatorData,
  OperatorSession,
} from "@/features/operator/types/operator";
import { fetchPendingApprovals } from "@/lib/approvals-api";
import { fetchIntegrations } from "@/lib/integrations-api";
import { getEnvironmentHeader } from "@/lib/environment";
import {
  createOperatorActionPlan,
  createOperatorSession,
  fetchOperatorSessionDetail,
  fetchOperatorSessions,
  fetchOperators,
  runOperatorAction,
  type OperatorAction,
  type OperatorSummary,
} from "@/lib/operators-api";
import { fetchSources } from "@/lib/rag-api";
import { fetchWorkflows } from "@/lib/workflows-api";
import { useAuth } from "@/lib/use-auth";

type OperatorDataWithActions = OperatorData & {
  operators: OperatorSummary[];
  activeOperatorId: string | null;
  setActiveOperatorId: (id: string | null) => void;
  activeSessionId: string | null;
  setActiveSessionId: (id: string | null) => void;
  createSession: (title: string, currentTask?: string) => Promise<void>;
  createPlan: (prompt: string) => Promise<void>;
  runAction: (stepId: string) => Promise<void>;
  executionHistory: OperatorAction[];
  sessionStatus?: string | null;
  isPlanning: boolean;
  isExecuting: boolean;
  activePack: { type: ContextPackType; id: string } | null;
  setActivePack: (pack: { type: ContextPackType; id: string } | null) => void;
};

function formatTimestamp(value?: string | null): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return date.toLocaleString();
}

export function useOperatorData(): OperatorDataWithActions {
  const auth = useAuth();
  const environment = getEnvironmentHeader();
  const [operators, setOperators] = useState<OperatorSummary[]>([]);
  const [activeOperatorId, setActiveOperatorId] = useState<string | null>(null);
  const [sessions, setSessions] = useState<OperatorSession[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [executionHistory, setExecutionHistory] = useState<OperatorAction[]>([]);
  const [contextPacks, setContextPacks] = useState<ContextPack[]>([]);
  const [activePack, setActivePack] = useState<{ type: ContextPackType; id: string } | null>(null);
  const [activeContextPack, setActiveContextPack] = useState<OperatorContextPack | null>(null);
  const [actionPlan, setActionPlan] = useState<ActionPlan | null>(null);
  const [guardrails, setGuardrails] = useState<GuardrailSummary | null>(null);
  const [sessionStatus, setSessionStatus] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isPlanning, setIsPlanning] = useState(false);
  const [isExecuting, setIsExecuting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (auth.status !== "authenticated") {
      setIsLoading(auth.status === "loading");
      setError(auth.status === "unauthenticated" ? "Sign in to load operator context." : null);
      return;
    }
    let cancelled = false;
    async function loadOperators() {
      try {
        setIsLoading(true);
        setError(null);
        const includeInactive = auth.role === "admin";
        const data = await fetchOperators(auth.token, includeInactive);
        if (cancelled) return;
        setOperators(data.operators);
        if (!activeOperatorId && data.operators.length > 0) {
          setActiveOperatorId(data.operators[0].id);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to load operators.");
        }
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    }
    loadOperators();
    return () => {
      cancelled = true;
    };
  }, [auth.status, auth.token, auth.role]);

  useEffect(() => {
    if (auth.status !== "authenticated") return;
    if (!activeOperatorId) return;
    let cancelled = false;
    async function loadSessions() {
      try {
        setIsLoading(true);
        setError(null);
        const scope = auth.role === "admin" ? "all" : "mine";
        const data = await fetchOperatorSessions(auth.token, activeOperatorId, scope);
        if (cancelled) return;
        const mapped = data.sessions.map((session) => ({
          id: session.id,
          operator_id: session.operator_id,
          operator_version_id: session.operator_version_id ?? null,
          title: session.title,
          timestamp: formatTimestamp(session.updated_at ?? session.created_at),
          environment: session.environment,
          contextEntity: session.current_task
            ? `Task · ${session.current_task}`
            : "Operator session",
          primaryContext: { type: "run" as const, id: null },
          status: session.status,
          current_task: session.current_task,
          created_at: session.created_at,
        }));
        setSessions(mapped);
        if (!activeSessionId && mapped.length > 0) {
          setActiveSessionId(mapped[0].id);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to load sessions.");
        }
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    }
    loadSessions();
    return () => {
      cancelled = true;
    };
  }, [auth.status, auth.token, auth.role, activeOperatorId]);

  useEffect(() => {
    if (auth.status !== "authenticated") return;
    if (!activeSessionId) return;
    let cancelled = false;
    async function loadSessionDetail() {
      try {
        setIsLoading(true);
        setError(null);
        const detail = await fetchOperatorSessionDetail(auth.token, activeSessionId);
        if (cancelled) return;
        setSessionStatus(detail.session.status ?? null);
        if (detail.latest_plan) {
          setActionPlan({
            plan_id: detail.latest_plan.plan_id,
            title: detail.latest_plan.title,
            summary: detail.latest_plan.summary,
            steps: (detail.latest_plan.steps as any[]) ?? [],
          });
          setGuardrails((detail.latest_plan.guardrails as GuardrailSummary) ?? null);
        } else {
          setActionPlan(null);
          setGuardrails(null);
        }
        setExecutionHistory(detail.actions ?? []);
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to load session details.");
        }
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    }
    loadSessionDetail();
    return () => {
      cancelled = true;
    };
  }, [auth.status, auth.token, activeSessionId]);

  useEffect(() => {
    if (auth.status !== "authenticated") return;
    let cancelled = false;
    async function loadContextPacks() {
      try {
        setIsLoading(true);
        setError(null);
        const [workflows, integrations, sources, approvals] = await Promise.all([
          fetchWorkflows(auth.token),
          fetchIntegrations(auth.token),
          fetchSources(auth.token),
          fetchPendingApprovals(auth.token),
        ]);

        const runId = approvals.items[0]?.run_id ?? null;
        const workflowId = workflows.workflows[0]?.id ?? null;
        const connectorId = integrations.integrations[0]?.id ?? null;
        const sourceId = sources.sources[0]?.id ?? null;

        const packs: ContextPack[] = [
          {
            id: runId,
            type: "run",
            title: "Run Context Pack",
            summary: runId ? "Run summary, steps, approvals, and audit highlights." : "No run selected.",
            status: runId ? "ready" : "missing",
            environment,
            href: runId ? `/runs/${runId}` : "/runs",
          },
          {
            id: workflowId,
            type: "workflow",
            title: "Workflow Context Pack",
            summary: workflowId ? "Workflow versions, runs, and integration links." : "No workflow selected.",
            status: workflowId ? "ready" : "missing",
            environment,
            href: workflowId ? `/workflows/${workflowId}` : "/workflows",
          },
          {
            id: connectorId,
            type: "connector",
            title: "Integration Context Pack",
            summary: connectorId ? "Integration status and safe configuration summary." : "No integration selected.",
            status: connectorId ? "ready" : "missing",
            environment,
            href: connectorId ? `/integrations/${connectorId}` : "/integrations",
          },
          {
            id: sourceId,
            type: "source",
            title: "Source Context Pack",
            summary: sourceId ? "Source freshness and ingest jobs." : "No source selected.",
            status: sourceId ? "ready" : "missing",
            environment,
            href: sourceId ? `/sources/${sourceId}` : "/sources",
          },
        ];

        if (!cancelled) {
          setContextPacks(packs);
          const defaultPack = packs.find((pack) => pack.id);
          if (defaultPack?.id) {
            setActivePack({ type: defaultPack.type, id: defaultPack.id });
          }
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to load context packs.");
        }
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    }

    loadContextPacks();
    return () => {
      cancelled = true;
    };
  }, [auth.status, auth.token, environment]);

  useEffect(() => {
    if (auth.status !== "authenticated") return;
    if (!activePack?.id) return;
    let cancelled = false;
    async function loadActivePack() {
      try {
        setIsLoading(true);
        const data = await fetchContextPack(auth.token, activePack.type, activePack.id);
        if (!cancelled) {
          setActiveContextPack(data);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to load context pack.");
        }
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    }
    loadActivePack();
    return () => {
      cancelled = true;
    };
  }, [auth.status, auth.token, activePack]);

  const createSession = useCallback(
    async (title: string, currentTask?: string) => {
      if (auth.status !== "authenticated" || !activeOperatorId) return;
      setIsLoading(true);
      setError(null);
      try {
        const session = await createOperatorSession(auth.token, activeOperatorId, {
          title,
          current_task: currentTask ?? null,
        });
        const mapped: OperatorSession = {
          id: session.id,
          operator_id: session.operator_id,
          operator_version_id: session.operator_version_id ?? null,
          title: session.title,
          timestamp: formatTimestamp(session.updated_at ?? session.created_at),
          environment: session.environment,
          contextEntity: session.current_task
            ? `Task · ${session.current_task}`
            : "Operator session",
          primaryContext: { type: "run", id: null },
          status: session.status,
          current_task: session.current_task,
          created_at: session.created_at,
        };
        setSessions((prev) => [mapped, ...prev]);
        setActiveSessionId(session.id);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to create session.");
      } finally {
        setIsLoading(false);
      }
    },
    [auth.status, auth.token, activeOperatorId]
  );

  const createPlan = useCallback(
    async (prompt: string) => {
      if (auth.status !== "authenticated" || !activeOperatorId || !activeSessionId) return;
      if (!activePack?.id) {
        setError("Select a context pack to generate a plan.");
        return;
      }
      setIsPlanning(true);
      setError(null);
      try {
        const related = contextPacks
          .filter((pack) => pack.id && pack.type !== activePack.type)
          .map((pack) => ({ type: pack.type, id: pack.id as string }));
        const plan = await createOperatorActionPlan(auth.token, activeOperatorId, {
          session_id: activeSessionId,
          primary_context: { type: activePack.type, id: activePack.id },
          related_contexts: related,
          operator_goal: prompt,
          prompt,
        });
        setActionPlan({
          plan_id: plan.plan_id,
          title: plan.title,
          summary: plan.summary,
          steps: (plan.steps as any[]) ?? [],
        });
        setGuardrails((plan.guardrails as GuardrailSummary) ?? null);
        const detail = await fetchOperatorSessionDetail(auth.token, activeSessionId);
        setExecutionHistory(detail.actions ?? []);
        setSessionStatus(detail.session.status ?? null);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to create action plan.");
      } finally {
        setIsPlanning(false);
      }
    },
    [auth.status, auth.token, activeOperatorId, activeSessionId, activePack, contextPacks]
  );

  const runAction = useCallback(
    async (stepId: string) => {
      if (auth.status !== "authenticated" || !activeOperatorId || !activeSessionId || !actionPlan) return;
      setIsExecuting(true);
      setError(null);
      try {
        await runOperatorAction(auth.token, activeOperatorId, {
          session_id: activeSessionId,
          plan_id: actionPlan.plan_id,
          step_id: stepId,
          confirm: true,
        });
        const detail = await fetchOperatorSessionDetail(auth.token, activeSessionId);
        setExecutionHistory(detail.actions ?? []);
        setSessionStatus(detail.session.status ?? null);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to execute action.");
      } finally {
        setIsExecuting(false);
      }
    },
    [auth.status, auth.token, activeOperatorId, activeSessionId, actionPlan]
  );

  const workspace = useMemo(() => {
    const summary =
      activeContextPack?.pack?.summary ??
      "Select a context pack to load summary details.";
    return {
      currentTask: "Investigate operator context",
      reasoning:
        "Operator analysis surfaces context and guardrails before any action is taken.",
      contextSummary: summary,
      researchResults: [
        {
          id: "research-1",
          title: "Run Summary",
          items: ["Status: pending", "Workflow: (select a context pack)", "Environment: " + environment],
        },
        {
          id: "research-2",
          title: "Integration Snapshot",
          items: ["Integration: (load context)", "Latency spike detected", "Retry policy: policy-driven"],
        },
      ],
    };
  }, [activeContextPack, environment]);

  return {
    operators,
    activeOperatorId,
    setActiveOperatorId,
    activeSessionId,
    setActiveSessionId,
    createSession,
    createPlan,
    runAction,
    executionHistory,
    sessionStatus,
    sessions,
    actionPlan,
    proposals:
      actionPlan?.steps.map((step) => ({
        id: step.id,
        stepId: step.id,
        title: step.title,
        description: step.description,
        environment: step.explanation.environment,
        requiresApproval: step.explanation.approval_required,
        requiresAdmin: step.explanation.admin_required,
        executionState: step.explanation.executable ? "executable" : "draft",
        confirmationRequired: step.explanation.confirmation_required,
        ctaLabel: step.explanation.executable ? "Request confirmation" : "View details",
      })) ?? [],
    contextPacks,
    activeContextPack,
    guardrails,
    workspace,
    isLoading,
    error,
    isPlanning,
    isExecuting,
    activePack,
    setActivePack,
  };
}
