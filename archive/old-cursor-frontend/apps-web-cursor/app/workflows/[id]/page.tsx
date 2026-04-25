"use client";

import { useRouter, useParams } from "next/navigation";
import Link from "next/link";
import { useEffect, useState, useCallback, useMemo } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/lib/use-auth";
import { WorkflowCanvas } from "@/features/workflows/components/workflow-canvas";
import { WorkflowConfigPanel } from "@/features/workflows/components/workflow-config-panel";
import { WorkflowToolbox } from "@/features/workflows/components/workflow-toolbox";
import {
  activateWorkflowVersion,
  ApiError,
  createWorkflowVersion,
  fetchActiveWorkflowVersion,
  fetchWorkflow,
  fetchWorkflowVersions,
  fetchWorkflowNodes,
  fetchWorkflowEdges,
  createWorkflowNode,
  updateWorkflowNode,
  deleteWorkflowNode,
  createWorkflowEdge,
  deleteWorkflowEdge,
  postExecute,
  postDryRun,
  promoteWorkflowVersion,
  type ActiveWorkflowVersion,
  type WorkflowVersionItem,
  type WorkflowNode,
  type WorkflowEdge,
} from "@/lib/workflows-api";
import { getDefaultDefinitionJson } from "@/lib/default-definition";
import { getEnvironmentHeader } from "@/lib/environment";
import { fetchOperators, type OperatorSummary } from "@/lib/operators-api";
import { fetchIntegrations, type IntegrationItem } from "@/lib/integrations-api";
import { fetchSources, type RagSource } from "@/lib/rag-api";

function parseJson(s: string): { ok: true; value: Record<string, unknown> } | { ok: false; error: string } {
  try {
    const v = JSON.parse(s);
    if (v == null || typeof v !== "object") return { ok: false, error: "Definition must be a JSON object" };
    return { ok: true, value: v as Record<string, unknown> };
  } catch (e) {
    return { ok: false, error: e instanceof Error ? e.message : "Invalid JSON" };
  }
}

export default function WorkflowDetailPage() {
  const router = useRouter();
  const params = useParams();
  const id = params.id as string;
  const isNew = id === "new";
  const auth = useAuth();
  const [definitionJson, setDefinitionJson] = useState("");
  const [parametersJson, setParametersJson] = useState('{"query": "example search"}');
  const [jsonError, setJsonError] = useState<string | null>(null);
  const [loading, setLoading] = useState(!isNew);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [dryRunLoading, setDryRunLoading] = useState(false);
  const [dryRunError, setDryRunError] = useState<string | null>(null);
  const [lastRunId, setLastRunId] = useState<string | null>(null);
  const [executeLoading, setExecuteLoading] = useState(false);
  const [executeError, setExecuteError] = useState<string | null>(null);
  const [versions, setVersions] = useState<WorkflowVersionItem[]>([]);
  const [activeVersion, setActiveVersion] = useState<ActiveWorkflowVersion | null>(null);
  const [versionsLoading, setVersionsLoading] = useState(false);
  const [versionActionLoading, setVersionActionLoading] = useState(false);
  const [versionActionType, setVersionActionType] = useState<"create" | "activate" | "promote" | null>(
    null
  );
  const [versionError, setVersionError] = useState<string | null>(null);
  const [versionActionAllowed, setVersionActionAllowed] = useState(true);
  const [promotionMessage, setPromotionMessage] = useState<string | null>(null);
  const [nodes, setNodes] = useState<WorkflowNode[]>([]);
  const [edges, setEdges] = useState<WorkflowEdge[]>([]);
  const [nodesLoading, setNodesLoading] = useState(false);
  const [nodesError, setNodesError] = useState<string | null>(null);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [operators, setOperators] = useState<OperatorSummary[]>([]);
  const [integrations, setIntegrations] = useState<IntegrationItem[]>([]);
  const [sources, setSources] = useState<RagSource[]>([]);
  const [toolboxError, setToolboxError] = useState<string | null>(null);
  const environment = getEnvironmentHeader();
  const canManage = auth.status === "authenticated" && auth.role === "admin";
  const canEditNodes = canManage && !isNew;
  const selectedNode = useMemo(
    () => nodes.find((node) => node.id === selectedNodeId) ?? null,
    [nodes, selectedNodeId]
  );

  const loadWorkflow = useCallback(() => {
    if (!isNew && auth.status === "authenticated" && auth.orgId) {
      setLoading(true);
      setDetailError(null);
      fetchWorkflow(auth.token, id)
        .then((w) => {
          setDefinitionJson(JSON.stringify(w.definition, null, 2));
        })
        .catch((e) => setDetailError(e.message ?? "Failed to load"))
        .finally(() => setLoading(false));
    } else if (isNew) {
      setDefinitionJson(getDefaultDefinitionJson());
      setLoading(false);
    }
  }, [id, isNew, auth.status, auth.token, auth.orgId]);

  const loadVersions = useCallback((options?: { showSkeleton?: boolean }) => {
    if (isNew || auth.status !== "authenticated" || !auth.orgId) return;
    const showSkeleton = options?.showSkeleton ?? true;
    if (showSkeleton) {
      setVersionsLoading(true);
    }
    setVersionError(null);
    Promise.all([
      fetchWorkflowVersions(auth.token, id),
      fetchActiveWorkflowVersion(auth.token, id).catch(() => null),
    ])
      .then(([list, active]) => {
        setVersions(list.versions);
        setActiveVersion(active);
      })
      .catch((e) => setVersionError(e.message ?? "Failed to load versions"))
      .finally(() => {
        if (showSkeleton) {
          setVersionsLoading(false);
        }
      });
  }, [id, isNew, auth.status, auth.token, auth.orgId]);

  const loadNodes = useCallback(() => {
    if (isNew || auth.status !== "authenticated" || !auth.orgId) return;
    setNodesLoading(true);
    setNodesError(null);
    Promise.all([fetchWorkflowNodes(auth.token, id), fetchWorkflowEdges(auth.token, id)])
      .then(([nodesRes, edgesRes]) => {
        setNodes(nodesRes.nodes);
        setEdges(edgesRes.edges);
        if (nodesRes.nodes.length > 0) {
          setSelectedNodeId((current) => current ?? nodesRes.nodes[0].id);
        }
      })
      .catch((e) => setNodesError(e.message ?? "Failed to load orchestration"))
      .finally(() => setNodesLoading(false));
  }, [id, isNew, auth.status, auth.token, auth.orgId]);

  const loadToolbox = useCallback(() => {
    if (auth.status !== "authenticated" || !auth.orgId) return;
    setToolboxError(null);
    Promise.all([
      fetchOperators(auth.token).then((res) => res.operators),
      fetchIntegrations(auth.token).then((res) => res.integrations),
      fetchSources(auth.token).then((res) => res.sources),
    ])
      .then(([ops, ints, srcs]) => {
        setOperators(ops);
        setIntegrations(ints);
        setSources(srcs);
      })
      .catch((e) => setToolboxError(e.message ?? "Failed to load toolbox data"));
  }, [auth.status, auth.token, auth.orgId]);

  const defaultNodePosition = (index: number) => ({
    x: 40 + (index % 3) * 260,
    y: 40 + Math.floor(index / 3) * 160,
  });

  useEffect(() => {
    loadWorkflow();
  }, [loadWorkflow]);

  useEffect(() => {
    loadVersions({ showSkeleton: true });
  }, [loadVersions]);

  useEffect(() => {
    loadNodes();
  }, [loadNodes]);

  useEffect(() => {
    loadToolbox();
  }, [loadToolbox]);

  const handleAddNode = async (payload: {
    node_type: WorkflowNode["node_type"];
    title: string;
    operator_id?: string | null;
    connector_id?: string | null;
    source_id?: string | null;
    tool_type?: string | null;
  }) => {
    if (auth.status !== "authenticated" || !auth.orgId || isNew || !canEditNodes) return;
    setNodesError(null);
    const position = defaultNodePosition(nodes.length);
    try {
      const created = await createWorkflowNode(auth.token, id, {
        ...payload,
        instruction: "",
        tool_config: null,
        position,
        metadata: {},
      });
      setNodes((prev) => [...prev, created]);
      setSelectedNodeId(created.id);
    } catch (e) {
      const message = e instanceof Error ? e.message : "Failed to create node";
      setNodesError(message);
    }
  };

  const handleSaveNode = async (payload: Partial<WorkflowNode>) => {
    if (auth.status !== "authenticated" || !auth.orgId || !selectedNode || !canEditNodes) return;
    setNodesError(null);
    try {
      const updated = await updateWorkflowNode(auth.token, selectedNode.id, payload);
      setNodes((prev) => prev.map((node) => (node.id === updated.id ? updated : node)));
    } catch (e) {
      const message = e instanceof Error ? e.message : "Failed to update node";
      setNodesError(message);
    }
  };

  const handleDeleteNode = async (nodeId: string) => {
    if (auth.status !== "authenticated" || !auth.orgId || !canEditNodes) return;
    setNodesError(null);
    try {
      await deleteWorkflowNode(auth.token, nodeId);
      setNodes((prev) => prev.filter((node) => node.id !== nodeId));
      setEdges((prev) => prev.filter((edge) => edge.from_node_id !== nodeId && edge.to_node_id !== nodeId));
      if (selectedNodeId === nodeId) {
        setSelectedNodeId(null);
      }
    } catch (e) {
      const message = e instanceof Error ? e.message : "Failed to delete node";
      setNodesError(message);
    }
  };

  const handleCreateEdge = async (payload: { to_node_id: string; edge_type: WorkflowEdge["edge_type"] }) => {
    if (auth.status !== "authenticated" || !auth.orgId || !selectedNode || !canEditNodes) return;
    setNodesError(null);
    try {
      const created = await createWorkflowEdge(auth.token, id, {
        from_node_id: selectedNode.id,
        to_node_id: payload.to_node_id,
        edge_type: payload.edge_type,
        condition: null,
      });
      setEdges((prev) => [...prev, created]);
    } catch (e) {
      const message = e instanceof Error ? e.message : "Failed to create edge";
      setNodesError(message);
    }
  };

  const handleDeleteEdge = async (edgeId: string) => {
    if (auth.status !== "authenticated" || !auth.orgId || !canEditNodes) return;
    try {
      await deleteWorkflowEdge(auth.token, edgeId);
      setEdges((prev) => prev.filter((edge) => edge.id !== edgeId));
    } catch (e) {
      const message = e instanceof Error ? e.message : "Failed to delete edge";
      setNodesError(message);
    }
  };

  const handleDryRun = () => {
    setJsonError(null);
    setDryRunError(null);
    const def = parseJson(definitionJson);
    if (!def.ok) {
      setJsonError(def.error);
      return;
    }
    let paramsObj: Record<string, unknown> = {};
    try {
      if (parametersJson.trim()) paramsObj = JSON.parse(parametersJson) as Record<string, unknown>;
    } catch {
      setJsonError("Parameters must be valid JSON");
      return;
    }
    if (auth.status !== "authenticated" || !auth.orgId) return;
    setDryRunLoading(true);
    postDryRun(auth.token, {
      ...(isNew ? { definition: def.value } : { workflow_id: id }),
      parameters: Object.keys(paramsObj).length ? paramsObj : undefined,
    })
      .then((res) => {
        setLastRunId(res.run_id);
        router.push(`/runs/${res.run_id}`);
      })
      .catch((e) => setDryRunError(e.message ?? "Dry-run failed"))
      .finally(() => setDryRunLoading(false));
  };

  const handleExecute = () => {
    setJsonError(null);
    setExecuteError(null);
    let paramsObj: Record<string, unknown> = {};
    try {
      if (parametersJson.trim()) paramsObj = JSON.parse(parametersJson) as Record<string, unknown>;
    } catch {
      setJsonError("Parameters must be valid JSON");
      return;
    }
    if (auth.status !== "authenticated" || !auth.orgId || isNew) return;
    setExecuteLoading(true);
    postExecute(auth.token, {
      workflow_id: id,
      parameters: Object.keys(paramsObj).length ? paramsObj : undefined,
    })
      .then((res) => {
        setLastRunId(res.run_id);
        router.push(`/runs/${res.run_id}`);
      })
      .catch((e) => setExecuteError(e.message ?? "Execute failed"))
      .finally(() => setExecuteLoading(false));
  };

  const handleCreateVersion = async () => {
    if (auth.status !== "authenticated" || !auth.orgId) return;
    setVersionError(null);
    setPromotionMessage(null);
    setVersionActionLoading(true);
    setVersionActionType("create");
    try {
      await createWorkflowVersion(auth.token, id);
      loadVersions({ showSkeleton: false });
    } catch (e) {
      const message = e instanceof Error ? e.message : "Failed to create version";
      setVersionError(message);
      if (e instanceof ApiError && e.status === 403) {
        setVersionActionAllowed(false);
      }
    } finally {
      setVersionActionLoading(false);
      setVersionActionType(null);
    }
  };

  const handleActivateVersion = async (versionId: string) => {
    if (auth.status !== "authenticated" || !auth.orgId) return;
    setVersionError(null);
    setPromotionMessage(null);
    setVersionActionLoading(true);
    setVersionActionType("activate");
    try {
      await activateWorkflowVersion(auth.token, id, versionId);
      loadVersions({ showSkeleton: false });
    } catch (e) {
      const message = e instanceof Error ? e.message : "Failed to activate version";
      setVersionError(message);
      if (e instanceof ApiError && e.status === 403) {
        setVersionActionAllowed(false);
      }
    } finally {
      setVersionActionLoading(false);
      setVersionActionType(null);
    }
  };

  const handlePromote = async (
    versionId: string,
    versionNumber: number,
    toEnv: "staging" | "production"
  ) => {
    if (auth.status !== "authenticated" || !auth.orgId) return;
    if (typeof window !== "undefined") {
      const ok = window.confirm(
        `Promote v${versionNumber} from ${environment} to ${toEnv}? This will create a new version in ${toEnv}.`
      );
      if (!ok) return;
    }
    setVersionError(null);
    setPromotionMessage(null);
    setVersionActionLoading(true);
    setVersionActionType("promote");
    try {
      const result = await promoteWorkflowVersion(auth.token, id, versionId, toEnv);
      setPromotionMessage(
        `From ${environment} → ${result.environment}: v${result.version} (${result.target_version_id.slice(0, 8)}…)`
      );
    } catch (e) {
      const message = e instanceof Error ? e.message : "Failed to promote version";
      setVersionError(message);
      if (e instanceof ApiError && e.status === 403) {
        setVersionActionAllowed(false);
      }
    } finally {
      setVersionActionLoading(false);
      setVersionActionType(null);
    }
  };

  if (auth.status === "loading" || auth.status === "unauthenticated") {
    return (
      <Card className="border-border bg-[hsl(var(--surface))]">
        <CardContent className="pt-6">
          <p className="text-sm text-muted-foreground">
            {auth.status === "loading" ? "Loading…" : "Sign in to view workflows."}
          </p>
        </CardContent>
      </Card>
    );
  }

  if (auth.orgId == null) {
    return (
      <Card className="border-border bg-[hsl(var(--surface))]">
        <CardContent className="pt-6">
          <p className="text-sm text-muted-foreground">
            Onboarding pending. Contact admin for org access.
          </p>
        </CardContent>
      </Card>
    );
  }

  if (!isNew && loading) {
    return (
      <Card className="border-border bg-[hsl(var(--surface))]">
        <CardContent className="pt-6">
          <p className="text-sm text-muted-foreground">Loading workflow…</p>
        </CardContent>
      </Card>
    );
  }

  if (!isNew && detailError) {
    return (
      <Card className="border-border bg-[hsl(var(--surface))]">
        <CardContent className="pt-6">
          <p className="text-sm text-destructive">{detailError}</p>
          <Link href="/workflows" className="mt-2 inline-block text-sm text-primary hover:underline">
            Back to workflows
          </Link>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-4">
        <div className="flex items-center gap-4">
          <Link
            href="/workflows"
            className="text-sm text-muted-foreground hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring rounded-sm"
          >
            ← Workflows
          </Link>
          <h1 className="text-3xl font-semibold tracking-tight text-foreground">
            {isNew ? "New workflow" : "Workflow"}
          </h1>
        </div>
        {!isNew && (
          <Link href={`/workflows/${id}/schedules`} passHref legacyBehavior>
            <Button variant="secondary" size="sm" asChild>
              <a>Schedules</a>
            </Button>
          </Link>
        )}
      </div>

      <div className="grid gap-4 lg:grid-cols-[240px,1fr,320px]">
        <Card className="border-border bg-[hsl(var(--surface))]">
          <CardHeader>
            <CardTitle className="text-sm uppercase tracking-[0.2em] text-muted-foreground">
              Toolbox
            </CardTitle>
          </CardHeader>
          <CardContent>
            {toolboxError ? (
              <p className="text-xs text-destructive">{toolboxError}</p>
            ) : (
              <WorkflowToolbox
                operators={operators}
                integrations={integrations}
                sources={sources}
                canManage={canEditNodes}
                onAddNode={handleAddNode}
              />
            )}
          </CardContent>
        </Card>

        <Card className="border-border bg-[hsl(var(--surface))]">
          <CardHeader>
            <div className="flex flex-wrap items-center justify-between gap-2">
              <CardTitle className="text-lg">Orchestration builder</CardTitle>
              <span className="rounded-full border border-border bg-muted px-2 py-0.5 text-xs text-muted-foreground">
                Environment: {environment}
              </span>
            </div>
            <p className="text-xs text-muted-foreground">
              Add agents, tasks, integrations, and sources. Connect nodes to define the workflow flow.
            </p>
          </CardHeader>
          <CardContent className="space-y-3">
            {nodesError && <p className="text-sm text-destructive">{nodesError}</p>}
            {isNew ? (
              <div className="rounded-md border border-dashed border-border p-6 text-sm text-muted-foreground">
                Create the workflow definition first. Orchestration nodes are available after the workflow exists.
              </div>
            ) : nodesLoading ? (
              <div className="rounded-md border border-border p-6 text-sm text-muted-foreground">
                Loading orchestration…
              </div>
            ) : (
              <WorkflowCanvas
                nodes={nodes}
                edges={edges}
                selectedNodeId={selectedNodeId}
                onSelect={setSelectedNodeId}
              />
            )}
            <div className="flex items-center gap-3 text-xs text-muted-foreground">
              <Link href="/runs" className="text-primary hover:underline">
                View runs
              </Link>
              <span>Use runs for execution logs and approval checkpoints.</span>
            </div>
          </CardContent>
        </Card>

        <Card className="border-border bg-[hsl(var(--surface))]">
          <CardHeader>
            <CardTitle className="text-sm uppercase tracking-[0.2em] text-muted-foreground">
              Configuration
            </CardTitle>
          </CardHeader>
          <CardContent className="h-full">
            <WorkflowConfigPanel
              node={selectedNode}
              nodes={nodes}
              edges={edges}
              operators={operators}
              integrations={integrations}
              sources={sources}
              canManage={canEditNodes}
              onSaveNode={handleSaveNode}
              onDeleteNode={handleDeleteNode}
              onCreateEdge={handleCreateEdge}
              onDeleteEdge={handleDeleteEdge}
            />
          </CardContent>
        </Card>
      </div>

      <Card className="border-border bg-[hsl(var(--surface))]">
        <CardHeader>
          <CardTitle className="text-lg">Definition (JSON)</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          {jsonError && (
            <p className="text-sm text-destructive" role="alert">
              {jsonError}
            </p>
          )}
          <textarea
            className="w-full min-h-[280px] rounded-md border border-border bg-background px-3 py-2 text-sm font-mono text-foreground placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:opacity-50"
            value={definitionJson}
            onChange={(e) => setDefinitionJson(e.target.value)}
            spellCheck={false}
            aria-label="Workflow definition JSON"
          />
        </CardContent>
      </Card>

      {!isNew && (
        <Card className="border-border bg-[hsl(var(--surface))]">
          <CardHeader>
            <CardTitle className="text-lg">Versions</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <p className="text-sm text-muted-foreground">
              Environment: <span className="font-medium text-foreground">{environment}</span>
            </p>
            {activeVersion ? (
              <p className="text-sm text-foreground">
                Active version: <span className="font-semibold">v{activeVersion.version}</span>
              </p>
            ) : (
              <p className="text-sm text-muted-foreground">
                No active version. Create and activate a version to enable execute.
              </p>
            )}
            {versionError && (
              <p className="text-sm text-destructive" role="alert">
                {versionError}
              </p>
            )}
            {promotionMessage && (
              <p className="text-sm text-muted-foreground">{promotionMessage}</p>
            )}
            <div className="flex items-center gap-3">
              <Button
                variant="primary"
                size="sm"
                onClick={handleCreateVersion}
                disabled={versionActionLoading || !versionActionAllowed}
              >
                {versionActionType === "create" ? "Creating…" : "Create version"}
              </Button>
              <p className="text-xs text-muted-foreground">
                Versions are created from the stored workflow definition.
              </p>
            </div>
            {versionsLoading ? (
              <div className="space-y-2" aria-label="Loading versions">
                <div className="h-4 w-40 rounded-md bg-muted/60 animate-pulse" />
                <div className="h-4 w-64 rounded-md bg-muted/60 animate-pulse" />
                <div className="h-4 w-56 rounded-md bg-muted/60 animate-pulse" />
              </div>
            ) : versions.length === 0 ? (
              <p className="text-sm text-muted-foreground">No versions yet.</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full min-w-[520px] text-left text-sm border-collapse">
                  <thead>
                    <tr className="border-b border-border">
                      <th className="py-2 pr-4 font-medium text-foreground">Version</th>
                      <th className="py-2 pr-4 font-medium text-foreground">Schema</th>
                      <th className="py-2 pr-4 font-medium text-foreground">Created</th>
                      <th className="py-2 font-medium text-foreground">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {versions.map((v) => (
                      <tr key={v.id} className="border-b border-border">
                        <td className="py-3 pr-4 text-foreground">
                          v{v.version}
                          {activeVersion?.id === v.id && (
                            <span className="ml-2 inline-flex items-center rounded-md border border-border bg-muted px-2 py-0.5 text-xs text-foreground">
                              Active
                            </span>
                          )}
                        </td>
                        <td className="py-3 pr-4 text-muted-foreground">{v.schema_version}</td>
                        <td className="py-3 pr-4 text-muted-foreground">
                          {new Date(v.created_at).toLocaleString()}
                        </td>
                        <td className="py-3">
                          <div className="flex items-center gap-2">
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => handleActivateVersion(v.id)}
                              disabled={versionActionLoading || !versionActionAllowed}
                            >
                              Activate
                            </Button>
                            {environment !== "staging" && (
                              <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => handlePromote(v.id, v.version, "staging")}
                                disabled={versionActionLoading || !versionActionAllowed}
                              >
                                Promote to staging
                              </Button>
                            )}
                            {environment !== "production" && (
                              <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => handlePromote(v.id, v.version, "production")}
                                disabled={versionActionLoading || !versionActionAllowed}
                              >
                                Promote to production
                              </Button>
                            )}
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            <p className="text-xs text-muted-foreground">
              Admin permission required to create, activate, or promote versions.
            </p>
          </CardContent>
        </Card>
      )}

      <Card className="border-border bg-[hsl(var(--surface))]">
        <CardHeader>
          <CardTitle className="text-lg">Parameters (optional)</CardTitle>
        </CardHeader>
        <CardContent>
          <textarea
            className="w-full min-h-[80px] rounded-md border border-border bg-background px-3 py-2 text-sm font-mono text-foreground placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:opacity-50"
            value={parametersJson}
            onChange={(e) => setParametersJson(e.target.value)}
            placeholder='{"query": "..."}'
            spellCheck={false}
            aria-label="Parameters JSON"
          />
        </CardContent>
      </Card>

      <div className="flex items-center gap-4">
        <Button
          variant="primary"
          size="md"
          onClick={handleDryRun}
          disabled={dryRunLoading}
          aria-busy={dryRunLoading}
        >
          {dryRunLoading ? "Running…" : "Dry run"}
        </Button>
        {!isNew && (
          <Button
            variant="outline"
            size="md"
            onClick={handleExecute}
            disabled={executeLoading || !activeVersion}
            aria-busy={executeLoading}
          >
            {executeLoading ? "Executing…" : "Execute"}
          </Button>
        )}
        {dryRunError && (
          <p className="text-sm text-destructive" role="alert">
            {dryRunError}
          </p>
        )}
        {executeError && (
          <p className="text-sm text-destructive" role="alert">
            {executeError}
          </p>
        )}
        {lastRunId && (
          <Link
            href={`/runs/${lastRunId}`}
            className="text-sm text-primary hover:underline"
          >
            View last run
          </Link>
        )}
      </div>
    </div>
  );
}
