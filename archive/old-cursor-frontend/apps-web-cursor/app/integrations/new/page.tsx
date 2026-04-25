"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import Link from "next/link";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/lib/use-auth";
import { ApiError, createIntegration } from "@/lib/integrations-api";
import { getEnvironmentHeader } from "@/lib/environment";

type IntegrationType = "slack" | "email" | "webhook";

export default function NewIntegrationPage() {
  const auth = useAuth();
  const router = useRouter();
  const [name, setName] = useState("");
  const [type, setType] = useState<IntegrationType>("slack");
  const [allowedHosts, setAllowedHosts] = useState("");
  const [defaultPath, setDefaultPath] = useState("/");
  const [timeoutSeconds, setTimeoutSeconds] = useState("5");
  const [maxPayloadBytes, setMaxPayloadBytes] = useState("65536");
  const [retryCount, setRetryCount] = useState("1");
  const [retryBackoffMs, setRetryBackoffMs] = useState("250");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [actionAllowed, setActionAllowed] = useState(true);
  const environment = getEnvironmentHeader();
  const isAdmin = auth.status === "authenticated" && auth.role === "admin";
  const canManage = isAdmin && actionAllowed;

  const handleSubmit = async () => {
    if (auth.status !== "authenticated" || !auth.orgId) return;
    setError(null);
    setLoading(true);
    try {
      const config: Record<string, unknown> = {};
      if (name.trim()) {
        config.name = name.trim();
      }
      if (type === "webhook") {
        const hosts = allowedHosts
          .split(",")
          .map((h) => h.trim())
          .filter(Boolean);
        if (hosts.length === 0) {
          throw new Error("Webhook allowed_hosts is required");
        }
        config.allowed_hosts = hosts;
        if (defaultPath.trim()) config.default_path = defaultPath.trim();
        if (timeoutSeconds.trim()) config.timeout_seconds = Number(timeoutSeconds);
        if (maxPayloadBytes.trim()) config.max_payload_bytes = Number(maxPayloadBytes);
        if (retryCount.trim()) config.retry_count = Number(retryCount);
        if (retryBackoffMs.trim()) config.retry_backoff_ms = Number(retryBackoffMs);
      }
      const created = await createIntegration(auth.token, { type, config });
      router.push(`/integrations/${created.id}`);
    } catch (e) {
      const message = e instanceof Error ? e.message : "Failed to create integration";
      setError(message);
      if (e instanceof ApiError && e.status === 403) {
        setActionAllowed(false);
      }
    } finally {
      setLoading(false);
    }
  };

  if (auth.status === "loading" || auth.status === "unauthenticated") {
    return (
      <Card className="border-border bg-[hsl(var(--surface))]">
        <CardContent className="pt-6">
          <p className="text-sm text-muted-foreground">
            {auth.status === "loading" ? "Loading…" : "Sign in to create integrations."}
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

  if (!isAdmin) {
    return (
      <Card className="border-border bg-[hsl(var(--surface))]">
        <CardContent className="pt-6">
          <p className="text-sm text-muted-foreground">
            Admin permission required to create integrations.
          </p>
          <p className="text-xs text-muted-foreground mt-2">
            Environment: <span className="font-medium text-foreground">{environment}</span>
          </p>
          <Link href="/integrations" className="mt-4 inline-block text-sm text-primary hover:underline">
            Back to integrations
          </Link>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <Link
          href="/integrations"
          className="text-sm text-muted-foreground hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring rounded-sm"
        >
          ← Integrations
        </Link>
        <h1 className="text-3xl font-semibold tracking-tight text-foreground">
          New integration
        </h1>
      </div>

      <Card className="border-border bg-[hsl(var(--surface))]">
        <CardHeader>
          <CardTitle className="text-lg">Details</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            <label className="text-sm font-medium text-foreground">Integration name</label>
            <input
              className="mt-1 w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Payments Slack"
              disabled={!canManage}
            />
          </div>
          <div>
            <label className="text-sm font-medium text-foreground">Type</label>
            <select
              className="mt-1 w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
              value={type}
              onChange={(e) => setType(e.target.value as IntegrationType)}
              disabled={!canManage}
            >
              <option value="slack">Slack</option>
              <option value="email">Email</option>
              <option value="webhook">Webhook</option>
            </select>
          </div>

          <div className="text-sm text-muted-foreground">
            Environment: <span className="font-medium text-foreground">{environment}</span>
          </div>

          {type === "webhook" ? (
            <div className="space-y-3">
              <div>
                <label className="text-sm font-medium text-foreground">
                  Allowed hosts (comma-separated)
                </label>
                <input
                  className="mt-1 w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
                  value={allowedHosts}
                  onChange={(e) => setAllowedHosts(e.target.value)}
                  placeholder="example.com, api.vendor.com"
                  disabled={!canManage}
                />
              </div>
              <div>
                <label className="text-sm font-medium text-foreground">Default path</label>
                <input
                  className="mt-1 w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
                  value={defaultPath}
                  onChange={(e) => setDefaultPath(e.target.value)}
                  placeholder="/webhook"
                  disabled={!canManage}
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-sm font-medium text-foreground">Timeout (sec)</label>
                  <input
                    className="mt-1 w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
                    value={timeoutSeconds}
                    onChange={(e) => setTimeoutSeconds(e.target.value)}
                    inputMode="numeric"
                    disabled={!canManage}
                  />
                </div>
                <div>
                  <label className="text-sm font-medium text-foreground">Max payload (bytes)</label>
                  <input
                    className="mt-1 w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
                    value={maxPayloadBytes}
                    onChange={(e) => setMaxPayloadBytes(e.target.value)}
                    inputMode="numeric"
                    disabled={!canManage}
                  />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-sm font-medium text-foreground">Retry count</label>
                  <input
                    className="mt-1 w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
                    value={retryCount}
                    onChange={(e) => setRetryCount(e.target.value)}
                    inputMode="numeric"
                    disabled={!canManage}
                  />
                </div>
                <div>
                  <label className="text-sm font-medium text-foreground">Retry backoff (ms)</label>
                  <input
                    className="mt-1 w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
                    value={retryBackoffMs}
                    onChange={(e) => setRetryBackoffMs(e.target.value)}
                    inputMode="numeric"
                    disabled={!canManage}
                  />
                </div>
              </div>
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">
              Additional configuration can be added after creation.
            </p>
          )}

          {error && <p className="text-sm text-destructive">{error}</p>}
          <div className="flex items-center gap-3">
            <Button variant="primary" size="md" onClick={handleSubmit} disabled={!canManage || loading}>
              {loading ? "Creating…" : "Create integration"}
            </Button>
            {!canManage && (
              <span className="text-xs text-muted-foreground">Admin permission required.</span>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
