"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/lib/use-auth";
import { ApiError, fetchIntegrations, type IntegrationItem } from "@/lib/integrations-api";
import {
  createOperator,
  fetchOperators,
  type OperatorDetail,
  type OperatorSummary,
} from "@/lib/operators-api";
import { getEnvironmentHeader } from "@/lib/environment";
import { fetchBillingStatus, type BillingStatus } from "@/lib/billing-api";
import { UpgradeCta } from "@/components/billing/upgrade-cta";

export default function AgentsPage() {
  const auth = useAuth();
  const environment = getEnvironmentHeader();
  const [operators, setOperators] = useState<OperatorSummary[]>([]);
  const [integrations, setIntegrations] = useState<IntegrationItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [isCreating, setIsCreating] = useState(false);
  const [billingStatus, setBillingStatus] = useState<BillingStatus | null>(null);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [systemPrompt, setSystemPrompt] = useState("");
  const [status, setStatus] = useState<"draft" | "active" | "inactive">("draft");
  const [allowedEnvs, setAllowedEnvs] = useState(environment);
  const [requiresAdmin, setRequiresAdmin] = useState(true);
  const [requiresApproval, setRequiresApproval] = useState(true);
  const [approvalRoles, setApprovalRoles] = useState("admin");
  const [selectedConnectorIds, setSelectedConnectorIds] = useState<string[]>([]);

  const isAdmin = auth.status === "authenticated" && auth.role === "admin";

  const load = () => {
    if (auth.status !== "authenticated" || auth.orgId == null) {
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    Promise.all([
      fetchOperators(auth.token, isAdmin),
      fetchIntegrations(auth.token),
    ])
      .then(([operatorsData, integrationsData]) => {
        setOperators(operatorsData.operators);
        setIntegrations(integrationsData.integrations);
      })
      .catch((e) => {
        setError(e instanceof Error ? e.message : "Failed to load operators.");
      })
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    load();
  }, [auth.status, auth.token, auth.orgId, isAdmin]);

  useEffect(() => {
    if (auth.status !== "authenticated") return;
    fetchBillingStatus(auth.token).then(setBillingStatus).catch(() => null);
  }, [auth.status, auth.token]);

  const connectorOptions = useMemo(
    () =>
      integrations.map((conn) => ({
        id: conn.id,
        label: `${conn.type} · ${conn.status}`,
      })),
    [integrations]
  );

  const toggleConnector = (id: string) => {
    setSelectedConnectorIds((prev) =>
      prev.includes(id) ? prev.filter((item) => item !== id) : [...prev, id]
    );
  };

  const handleCreate = async () => {
    if (auth.status !== "authenticated") return;
    setActionError(null);
    setIsCreating(true);
    try {
      const envs = allowedEnvs
        .split(",")
        .map((value) => value.trim())
        .filter(Boolean);
      const roles = approvalRoles
        .split(",")
        .map((value) => value.trim())
        .filter(Boolean);
      const created: OperatorDetail = await createOperator(auth.token, {
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
      setOperators((prev) => [created, ...prev]);
      setName("");
      setDescription("");
      setSystemPrompt("");
      setAllowedEnvs(environment);
      setSelectedConnectorIds([]);
    } catch (e) {
      if (e instanceof ApiError && e.status === 403) {
        setActionError("Admin permission required to create operators.");
      } else {
        setActionError(e instanceof Error ? e.message : "Failed to create operator.");
      }
    } finally {
      setIsCreating(false);
    }
  };

  if (auth.status === "loading" || auth.status === "unauthenticated") {
    return (
      <Card className="border-border bg-[hsl(var(--surface))]">
        <CardHeader>
          <CardTitle className="text-lg">Agents</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">
            {auth.status === "loading" ? "Loading…" : "Sign in to view agents."}
          </p>
        </CardContent>
      </Card>
    );
  }

  if (auth.orgId == null) {
    return (
      <Card className="border-border bg-[hsl(var(--surface))]">
        <CardHeader>
          <CardTitle className="text-lg">Agents</CardTitle>
        </CardHeader>
        <CardContent>
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
        <CardHeader>
          <CardTitle className="text-lg">Agents</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-destructive">{error}</p>
        </CardContent>
      </Card>
    );
  }

  const agentsLimit = billingStatus?.plan.agents_limit ?? null;
  const limitReached = agentsLimit !== null && operators.length >= agentsLimit;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-semibold tracking-tight text-foreground">
            Agents
          </h1>
          <p className="text-sm text-muted-foreground">
            Environment: <span className="font-medium text-foreground">{environment}</span>
          </p>
        </div>
      </div>

      {limitReached && (
        <UpgradeCta message="You have reached your agent limit. Upgrade to add more agents." />
      )}

      <Card className="border-border bg-[hsl(var(--surface))]">
        <CardHeader>
          <CardTitle className="text-lg">Deployed operators</CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <p className="text-sm text-muted-foreground">Loading…</p>
          ) : operators.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              No operators configured yet.
            </p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[640px] text-left text-sm border-collapse">
                <thead>
                  <tr className="border-b border-border">
                    <th className="py-2 pr-4 font-medium text-foreground">Name</th>
                    <th className="py-2 pr-4 font-medium text-foreground">Status</th>
                    <th className="py-2 pr-4 font-medium text-foreground">Active version</th>
                    <th className="py-2 pr-4 font-medium text-foreground">Approvals</th>
                    <th className="py-2 pr-4 font-medium text-foreground">Admin</th>
                    <th className="py-2 font-medium text-foreground">Environments</th>
                  </tr>
                </thead>
                <tbody>
                  {operators.map((op) => (
                    <tr key={op.id} className="border-b border-border hover:bg-muted/50">
                      <td className="py-3 pr-4">
                        <Link
                          href={`/agents/${op.id}`}
                          className="text-primary hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring rounded-sm"
                        >
                          {op.name}
                        </Link>
                        {op.description ? (
                          <p className="text-xs text-muted-foreground mt-1">
                            {op.description}
                          </p>
                        ) : null}
                      </td>
                      <td className="py-3 pr-4 text-muted-foreground">{op.status}</td>
                      <td className="py-3 pr-4 text-muted-foreground">
                        {op.active_version ? `v${op.active_version.version}` : "—"}
                      </td>
                      <td className="py-3 pr-4 text-muted-foreground">
                        {op.requires_approval ? "Required" : "Optional"}
                      </td>
                      <td className="py-3 pr-4 text-muted-foreground">
                        {op.requires_admin ? "Admin only" : "Member allowed"}
                      </td>
                      <td className="py-3 text-muted-foreground">
                        {op.allowed_environments.length > 0
                          ? op.allowed_environments.join(", ")
                          : "All"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      {isAdmin && (
        <Card className="border-border bg-[hsl(var(--surface))]">
          <CardHeader>
            <CardTitle className="text-lg">Create operator</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <label className="text-sm font-medium text-foreground">Name</label>
              <input
                className="mt-1 w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
                value={name}
                onChange={(event) => setName(event.target.value)}
                placeholder="e.g. Incident Response Operator"
                disabled={isCreating}
              />
            </div>
            <div>
              <label className="text-sm font-medium text-foreground">Description</label>
              <input
                className="mt-1 w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
                value={description}
                onChange={(event) => setDescription(event.target.value)}
                placeholder="Short operator mission statement."
                disabled={isCreating}
              />
            </div>
            <div>
              <label className="text-sm font-medium text-foreground">System prompt</label>
              <textarea
                className="mt-1 w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
                rows={3}
                value={systemPrompt}
                onChange={(event) => setSystemPrompt(event.target.value)}
                placeholder="Operator instructions and safety constraints."
                disabled={isCreating}
              />
            </div>
            <div className="grid gap-3 md:grid-cols-2">
              <div>
                <label className="text-sm font-medium text-foreground">Status</label>
                <select
                  className="mt-1 w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
                  value={status}
                  onChange={(event) => setStatus(event.target.value as "draft" | "active" | "inactive")}
                  disabled={isCreating}
                >
                  <option value="draft">Draft</option>
                  <option value="active">Active</option>
                  <option value="inactive">Inactive</option>
                </select>
              </div>
              <div>
                <label className="text-sm font-medium text-foreground">
                  Allowed environments
                </label>
                <input
                  className="mt-1 w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
                  value={allowedEnvs}
                  onChange={(event) => setAllowedEnvs(event.target.value)}
                  placeholder="staging, production"
                  disabled={isCreating}
                />
              </div>
            </div>
            <div className="grid gap-3 md:grid-cols-2">
              <label className="flex items-center gap-2 text-sm text-muted-foreground">
                <input
                  type="checkbox"
                  checked={requiresAdmin}
                  onChange={(event) => setRequiresAdmin(event.target.checked)}
                  disabled={isCreating}
                />
                Admin required for operator actions
              </label>
              <label className="flex items-center gap-2 text-sm text-muted-foreground">
                <input
                  type="checkbox"
                  checked={requiresApproval}
                  onChange={(event) => setRequiresApproval(event.target.checked)}
                  disabled={isCreating}
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
                placeholder="admin, approver"
                disabled={isCreating || !requiresApproval}
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
                        disabled={isCreating}
                      />
                      {conn.label}
                    </label>
                  ))}
                </div>
              )}
            </div>
            {actionError && (
              <p className="text-sm text-destructive" role="alert">
                {actionError}
              </p>
            )}
            <div className="flex items-center gap-3">
              <Button variant="primary" size="md" onClick={handleCreate} disabled={isCreating || !name.trim()}>
                {isCreating ? "Creating…" : "Create operator"}
              </Button>
              <Button variant="secondary" size="md" onClick={load} disabled={isCreating}>
                Refresh list
              </Button>
            </div>
          </CardContent>
        </Card>
      )}
      {!isAdmin && (
        <Card className="border-border bg-[hsl(var(--surface))]">
          <CardContent className="pt-6">
            <p className="text-sm text-muted-foreground">
              Admin permission required to create or update operators.
            </p>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
