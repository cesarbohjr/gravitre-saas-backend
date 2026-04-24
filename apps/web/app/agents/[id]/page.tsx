"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/lib/use-auth";
import { ApiError, fetchIntegrations, type IntegrationItem } from "@/lib/integrations-api";
import {
  activateOperatorVersion,
  createOperatorVersion,
  fetchOperator,
  fetchOperatorVersions,
  updateOperator,
  type OperatorDetail,
  type OperatorVersionSummary,
} from "@/lib/operators-api";
import { getEnvironmentHeader } from "@/lib/environment";

export default function AgentDetailPage() {
  const { id } = useParams<{ id: string }>();
  const auth = useAuth();
  const environment = getEnvironmentHeader();
  const [operator, setOperator] = useState<OperatorDetail | null>(null);
  const [integrations, setIntegrations] = useState<IntegrationItem[]>([]);
  const [versions, setVersions] = useState<OperatorVersionSummary[]>([]);
  const [versionError, setVersionError] = useState<string | null>(null);
  const [creatingVersion, setCreatingVersion] = useState(false);
  const [activatingVersion, setActivatingVersion] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [systemPrompt, setSystemPrompt] = useState("");
  const [status, setStatus] = useState<"draft" | "active" | "inactive">("draft");
  const [allowedEnvs, setAllowedEnvs] = useState("");
  const [requiresAdmin, setRequiresAdmin] = useState(false);
  const [requiresApproval, setRequiresApproval] = useState(false);
  const [approvalRoles, setApprovalRoles] = useState("");
  const [selectedConnectorIds, setSelectedConnectorIds] = useState<string[]>([]);

  const isAdmin = auth.status === "authenticated" && auth.role === "admin";

  useEffect(() => {
    if (auth.status !== "authenticated" || auth.orgId == null) {
      setLoading(false);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError(null);
    Promise.all([
      fetchOperator(auth.token, id),
      fetchIntegrations(auth.token),
      fetchOperatorVersions(auth.token, id),
    ])
      .then(([operatorData, integrationData, versionsData]) => {
        if (cancelled) return;
        setOperator(operatorData);
        setIntegrations(integrationData.integrations);
        setVersions(versionsData.versions);
        setName(operatorData.name);
        setDescription(operatorData.description ?? "");
        setSystemPrompt(operatorData.system_prompt ?? "");
        setStatus(operatorData.status);
        setAllowedEnvs(operatorData.allowed_environments.join(", "));
        setRequiresAdmin(operatorData.requires_admin);
        setRequiresApproval(operatorData.requires_approval);
        setApprovalRoles(operatorData.approval_roles.join(", "));
        setSelectedConnectorIds(operatorData.connectors.map((conn) => conn.id));
      })
      .catch((e) => {
        if (cancelled) return;
        setError(e instanceof Error ? e.message : "Failed to load operator.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [auth.status, auth.token, auth.orgId, id]);

  const connectorOptions = useMemo(
    () =>
      integrations.map((conn) => ({
        id: conn.id,
        label: `${conn.type} · ${conn.status}`,
      })),
    [integrations]
  );

  const toggleConnector = (connectorId: string) => {
    setSelectedConnectorIds((prev) =>
      prev.includes(connectorId)
        ? prev.filter((item) => item !== connectorId)
        : [...prev, connectorId]
    );
  };

  const handleCreateVersion = async () => {
    if (auth.status !== "authenticated" || !isAdmin) return;
    setCreatingVersion(true);
    setVersionError(null);
    try {
      const created = await createOperatorVersion(auth.token, id);
      setVersions((prev) => [created, ...prev]);
    } catch (e) {
      setVersionError(e instanceof Error ? e.message : "Failed to create version.");
    } finally {
      setCreatingVersion(false);
    }
  };

  const handleActivateVersion = async (versionId: string) => {
    if (auth.status !== "authenticated" || !isAdmin) return;
    setActivatingVersion(versionId);
    setVersionError(null);
    try {
      await activateOperatorVersion(auth.token, id, versionId);
      const [updatedOperator, versionsData] = await Promise.all([
        fetchOperator(auth.token, id),
        fetchOperatorVersions(auth.token, id),
      ]);
      setOperator(updatedOperator);
      setVersions(versionsData.versions);
    } catch (e) {
      setVersionError(e instanceof Error ? e.message : "Failed to activate version.");
    } finally {
      setActivatingVersion(null);
    }
  };

  const handleSave = async () => {
    if (auth.status !== "authenticated" || !isAdmin) return;
    setSaving(true);
    setActionError(null);
    try {
      const envs = allowedEnvs
        .split(",")
        .map((value) => value.trim())
        .filter(Boolean);
      const roles = approvalRoles
        .split(",")
        .map((value) => value.trim())
        .filter(Boolean);
      const updated = await updateOperator(auth.token, id, {
        name: name.trim(),
        description: description.trim() || null,
        status,
        system_prompt: systemPrompt.trim() || null,
        allowed_environments: envs,
        requires_admin: requiresAdmin,
        requires_approval: requiresApproval,
        approval_roles: roles,
        connector_ids: selectedConnectorIds,
      });
      setOperator(updated);
    } catch (e) {
      if (e instanceof ApiError && e.status === 403) {
        setActionError("Admin permission required to update operators.");
      } else {
        setActionError(e instanceof Error ? e.message : "Failed to update operator.");
      }
    } finally {
      setSaving(false);
    }
  };

  if (auth.status === "loading" || auth.status === "unauthenticated") {
    return (
      <Card className="border-border bg-[hsl(var(--surface))]">
        <CardContent className="pt-6">
          <p className="text-sm text-muted-foreground">
            {auth.status === "loading" ? "Loading…" : "Sign in to view operators."}
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

  if (error) {
    return (
      <Card className="border-border bg-[hsl(var(--surface))]">
        <CardContent className="pt-6">
          <p className="text-sm text-destructive">{error}</p>
        </CardContent>
      </Card>
    );
  }

  if (loading || !operator) {
    return (
      <Card className="border-border bg-[hsl(var(--surface))]">
        <CardContent className="pt-6">
          <p className="text-sm text-muted-foreground">Loading operator…</p>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <Link
          href="/agents"
          className="text-sm text-muted-foreground hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring rounded-sm"
        >
          ← Agents
        </Link>
        <h1 className="text-3xl font-semibold tracking-tight text-foreground">
          {operator.name}
        </h1>
      </div>

      <Card className="border-border bg-[hsl(var(--surface))]">
        <CardHeader>
          <CardTitle className="text-lg">Operator configuration</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            <label className="text-sm font-medium text-foreground">Name</label>
            <input
              className="mt-1 w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
              value={name}
              onChange={(event) => setName(event.target.value)}
              disabled={!isAdmin || saving}
            />
          </div>
          <div>
            <label className="text-sm font-medium text-foreground">Description</label>
            <input
              className="mt-1 w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
              value={description}
              onChange={(event) => setDescription(event.target.value)}
              disabled={!isAdmin || saving}
            />
          </div>
          <div>
            <label className="text-sm font-medium text-foreground">System prompt</label>
            <textarea
              className="mt-1 w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
              rows={4}
              value={systemPrompt}
              onChange={(event) => setSystemPrompt(event.target.value)}
              disabled={!isAdmin || saving}
            />
          </div>
          <div className="grid gap-3 md:grid-cols-2">
            <div>
              <label className="text-sm font-medium text-foreground">Status</label>
              <select
                className="mt-1 w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
                value={status}
                onChange={(event) => setStatus(event.target.value as "draft" | "active" | "inactive")}
                disabled={!isAdmin || saving}
              >
                <option value="draft">Draft</option>
                <option value="active">Active</option>
                <option value="inactive">Inactive</option>
              </select>
            </div>
            <div>
              <label className="text-sm font-medium text-foreground">Allowed environments</label>
              <input
                className="mt-1 w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
                value={allowedEnvs}
                onChange={(event) => setAllowedEnvs(event.target.value)}
                disabled={!isAdmin || saving}
              />
            </div>
          </div>
          <div className="grid gap-3 md:grid-cols-2">
            <label className="flex items-center gap-2 text-sm text-muted-foreground">
              <input
                type="checkbox"
                checked={requiresAdmin}
                onChange={(event) => setRequiresAdmin(event.target.checked)}
                disabled={!isAdmin || saving}
              />
              Admin required for operator actions
            </label>
            <label className="flex items-center gap-2 text-sm text-muted-foreground">
              <input
                type="checkbox"
                checked={requiresApproval}
                onChange={(event) => setRequiresApproval(event.target.checked)}
                disabled={!isAdmin || saving}
              />
              Approval required before execution
            </label>
          </div>
          <div>
            <label className="text-sm font-medium text-foreground">Approval roles</label>
            <input
              className="mt-1 w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
              value={approvalRoles}
              onChange={(event) => setApprovalRoles(event.target.value)}
              disabled={!isAdmin || saving || !requiresApproval}
            />
          </div>
          <div>
            <label className="text-sm font-medium text-foreground">Integration bindings</label>
            {connectorOptions.length === 0 ? (
              <p className="mt-2 text-sm text-muted-foreground">
                No integrations available in this environment.
              </p>
            ) : (
              <div className="mt-2 grid gap-2 md:grid-cols-2">
                {connectorOptions.map((conn) => (
                  <label key={conn.id} className="flex items-center gap-2 text-sm text-muted-foreground">
                    <input
                      type="checkbox"
                      checked={selectedConnectorIds.includes(conn.id)}
                      onChange={() => toggleConnector(conn.id)}
                      disabled={!isAdmin || saving}
                    />
                    {conn.label}
                  </label>
                ))}
              </div>
            )}
          </div>
          <p className="text-xs text-muted-foreground">
            Environment: <span className="font-medium text-foreground">{environment}</span>
          </p>
          {actionError && (
            <p className="text-sm text-destructive" role="alert">
              {actionError}
            </p>
          )}
          <div className="flex items-center gap-3">
            <Button variant="primary" size="md" onClick={handleSave} disabled={!isAdmin || saving}>
              {saving ? "Saving…" : "Save changes"}
            </Button>
            {!isAdmin && (
              <span className="text-xs text-muted-foreground">
                Admin permission required to edit.
              </span>
            )}
          </div>
        </CardContent>
      </Card>

      <Card className="border-border bg-[hsl(var(--surface))]">
        <CardHeader>
          <CardTitle className="text-lg">Operator versions</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className="text-sm text-muted-foreground">
                Active version:{" "}
                <span className="font-medium text-foreground">
                  {operator.active_version ? `v${operator.active_version.version}` : "None"}
                </span>
              </p>
              <p className="text-xs text-muted-foreground">
                Environment: <span className="font-medium text-foreground">{environment}</span>
              </p>
            </div>
            {isAdmin && (
              <Button
                variant="secondary"
                size="sm"
                onClick={handleCreateVersion}
                disabled={creatingVersion}
              >
                {creatingVersion ? "Creating…" : "Create version"}
              </Button>
            )}
          </div>
          {versionError && (
            <p className="text-sm text-destructive" role="alert">
              {versionError}
            </p>
          )}
          {versions.length === 0 ? (
            <p className="text-sm text-muted-foreground">No versions created yet.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[640px] text-left text-sm border-collapse">
                <thead>
                  <tr className="border-b border-border">
                    <th className="py-2 pr-4 font-medium text-foreground">Version</th>
                    <th className="py-2 pr-4 font-medium text-foreground">Name</th>
                    <th className="py-2 pr-4 font-medium text-foreground">Created</th>
                    <th className="py-2 font-medium text-foreground">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {versions.map((version) => {
                    const isActive = operator.active_version?.id === version.id;
                    return (
                      <tr key={version.id} className="border-b border-border">
                        <td className="py-3 pr-4 text-muted-foreground">
                          v{version.version}
                        </td>
                        <td className="py-3 pr-4 text-muted-foreground">
                          {version.name}
                        </td>
                        <td className="py-3 pr-4 text-muted-foreground">
                          {version.created_at
                            ? new Date(version.created_at).toLocaleString()
                            : "—"}
                        </td>
                        <td className="py-3">
                          <div className="flex items-center gap-2">
                            {isActive ? (
                              <span className="rounded-full bg-muted px-2 py-0.5 text-xs text-muted-foreground">
                                Active
                              </span>
                            ) : (
                              <Button
                                variant="outline"
                                size="sm"
                                onClick={() => handleActivateVersion(version.id)}
                                disabled={!isAdmin || activatingVersion === version.id}
                              >
                                {activatingVersion === version.id ? "Activating…" : "Activate"}
                              </Button>
                            )}
                            {!isAdmin && (
                              <span className="text-xs text-muted-foreground">
                                Read-only
                              </span>
                            )}
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
