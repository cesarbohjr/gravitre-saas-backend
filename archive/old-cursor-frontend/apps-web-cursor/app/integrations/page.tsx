"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/lib/use-auth";
import { ApiError, fetchIntegrations, type IntegrationItem } from "@/lib/integrations-api";
import { getEnvironmentHeader } from "@/lib/environment";

function formatIntegrationType(type: IntegrationItem["type"]): string {
  return type.charAt(0).toUpperCase() + type.slice(1);
}

export default function IntegrationsListPage() {
  const auth = useAuth();
  const [items, setItems] = useState<IntegrationItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [permissionRestricted, setPermissionRestricted] = useState(false);
  const environment = getEnvironmentHeader();
  const isAdmin = auth.status === "authenticated" && auth.role === "admin";

  useEffect(() => {
    if (auth.status !== "authenticated" || auth.orgId == null) {
      setLoading(false);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError(null);
    setPermissionRestricted(false);
    fetchIntegrations(auth.token)
      .then((data) => {
        if (!cancelled) setItems(data.integrations);
      })
      .catch((e) => {
        if (cancelled) return;
        if (e instanceof ApiError && e.status === 403) {
          setPermissionRestricted(true);
          return;
        }
        setError(e.message ?? "Failed to load");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [auth.status, auth.token, auth.orgId]);

  if (auth.status === "loading" || auth.status === "unauthenticated") {
    return (
      <Card className="border-border bg-[hsl(var(--surface))]">
        <CardHeader>
          <CardTitle className="text-lg">Integrations</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">
            {auth.status === "loading" ? "Loading…" : "Sign in to view integrations."}
          </p>
        </CardContent>
      </Card>
    );
  }

  if (auth.orgId == null) {
    return (
      <Card className="border-border bg-[hsl(var(--surface))]">
        <CardHeader>
          <CardTitle className="text-lg">Integrations</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">
            Onboarding pending. Contact admin for org access to manage integrations.
          </p>
        </CardContent>
      </Card>
    );
  }

  if (error) {
    return (
      <Card className="border-border bg-[hsl(var(--surface))]">
        <CardHeader>
          <CardTitle className="text-lg">Integrations</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-destructive">{error}</p>
        </CardContent>
      </Card>
    );
  }

  if (permissionRestricted) {
    return (
      <Card className="border-border bg-[hsl(var(--surface))]">
        <CardHeader>
          <CardTitle className="text-lg">Integrations</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">
            Admin permission required to view integrations in this environment.
          </p>
          <p className="text-xs text-muted-foreground mt-2">
            Environment: <span className="font-medium text-foreground">{environment}</span>
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-semibold tracking-tight text-foreground">
            Integrations
          </h1>
          <p className="text-sm text-muted-foreground">
            Environment: <span className="font-medium text-foreground">{environment}</span>
          </p>
        </div>
        {isAdmin ? (
          <Link href="/integrations/new" passHref legacyBehavior>
            <Button variant="primary" size="md" asChild disabled={loading}>
              <a>New integration</a>
            </Button>
          </Link>
        ) : (
          <Button variant="primary" size="md" disabled>
            New integration
          </Button>
        )}
      </div>

      <Card className="border-border bg-[hsl(var(--surface))]">
        <CardHeader>
          <CardTitle className="text-lg">Configured integrations</CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <p className="text-sm text-muted-foreground">Loading…</p>
          ) : items.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              No integrations yet. Create one to enable workflow execution.
            </p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[640px] text-left text-sm border-collapse">
                <thead>
                  <tr className="border-b border-border">
                    <th className="py-2 pr-4 font-medium text-foreground">Name</th>
                    <th className="py-2 pr-4 font-medium text-foreground">Type</th>
                    <th className="py-2 pr-4 font-medium text-foreground">Status</th>
                    <th className="py-2 pr-4 font-medium text-foreground">Environment</th>
                    <th className="py-2 font-medium text-foreground">Last updated</th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((c) => {
                    const configName =
                      typeof c.config?.name === "string" ? c.config.name.trim() : "";
                    const displayName = configName || `${formatIntegrationType(c.type)} integration`;
                    const updated = c.updated_at
                      ? new Date(c.updated_at).toLocaleString()
                      : "—";
                    return (
                      <tr key={c.id} className="border-b border-border hover:bg-muted/50">
                        <td className="py-3 pr-4">
                          <Link
                            href={`/integrations/${c.id}`}
                            className="text-primary hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring rounded-sm"
                          >
                            {displayName}
                          </Link>
                        </td>
                        <td className="py-3 pr-4 text-muted-foreground">
                          {formatIntegrationType(c.type)}
                        </td>
                        <td className="py-3 pr-4 text-muted-foreground">{c.status}</td>
                        <td className="py-3 pr-4 text-muted-foreground">
                          {c.environment ?? environment}
                        </td>
                        <td className="py-3 text-muted-foreground">{updated}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
          <p className="mt-3 text-xs text-muted-foreground">
            Admin permission required to create or edit integrations.
          </p>
          {!isAdmin && (
            <p className="text-xs text-muted-foreground">Read-only access.</p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
