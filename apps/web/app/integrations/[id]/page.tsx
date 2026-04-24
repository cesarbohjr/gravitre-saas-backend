"use client";

import { useParams } from "next/navigation";
import Link from "next/link";
import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/lib/use-auth";
import {
  ApiError,
  fetchIntegration,
  updateIntegration,
  setIntegrationSecret,
  type IntegrationItem,
} from "@/lib/integrations-api";
import { getEnvironmentHeader } from "@/lib/environment";

function parseJson(s: string): { ok: true; value: Record<string, unknown> } | { ok: false; error: string } {
  try {
    const v = JSON.parse(s);
    if (v == null || typeof v !== "object") return { ok: false, error: "Config must be a JSON object" };
    return { ok: true, value: v as Record<string, unknown> };
  } catch (e) {
    return { ok: false, error: e instanceof Error ? e.message : "Invalid JSON" };
  }
}

function formatIntegrationType(type: IntegrationItem["type"]): string {
  return type.charAt(0).toUpperCase() + type.slice(1);
}

export default function IntegrationDetailPage() {
  const params = useParams();
  const id = params.id as string;
  const auth = useAuth();
  const [integration, setIntegration] = useState<IntegrationItem | null>(null);
  const [configJson, setConfigJson] = useState("{}");
  const [status, setStatus] = useState<"active" | "inactive" | "error">("active");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saveLoading, setSaveLoading] = useState(false);
  const [secretKey, setSecretKey] = useState("");
  const [secretValue, setSecretValue] = useState("");
  const [secretStatus, setSecretStatus] = useState<string | null>(null);
  const [actionAllowed, setActionAllowed] = useState(true);
  const [permissionRestricted, setPermissionRestricted] = useState(false);
  const environment = getEnvironmentHeader();
  const isAdmin = auth.status === "authenticated" && auth.role === "admin";
  const canManage = isAdmin && actionAllowed;

  useEffect(() => {
    if (auth.status !== "authenticated" || !auth.orgId) {
      setLoading(false);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError(null);
    setPermissionRestricted(false);
    fetchIntegration(auth.token, id)
      .then((data) => {
        if (cancelled) return;
        setIntegration(data);
        setConfigJson(JSON.stringify(data.config ?? {}, null, 2));
        setStatus(data.status);
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
  }, [auth.status, auth.token, auth.orgId, id]);

  const handleSave = async () => {
    if (auth.status !== "authenticated" || !auth.orgId) return;
    setSaveError(null);
    const parsed = parseJson(configJson);
    if (!parsed.ok) {
      setSaveError(parsed.error);
      return;
    }
    setSaveLoading(true);
    try {
      const updated = await updateIntegration(auth.token, id, {
        config: parsed.value,
        status,
      });
      setIntegration(updated);
      setConfigJson(JSON.stringify(updated.config ?? {}, null, 2));
    } catch (e) {
      const message = e instanceof Error ? e.message : "Failed to update";
      setSaveError(message);
      if (e instanceof ApiError && e.status === 403) {
        setActionAllowed(false);
      }
    } finally {
      setSaveLoading(false);
    }
  };

  const handleSetSecret = async () => {
    if (auth.status !== "authenticated" || !auth.orgId) return;
    setSecretStatus(null);
    if (!secretKey.trim() || !secretValue.trim()) {
      setSecretStatus("Provide both key and value.");
      return;
    }
    try {
      await setIntegrationSecret(auth.token, id, {
        key_name: secretKey.trim(),
        value: secretValue,
      });
      setSecretStatus("Secret saved.");
      setSecretKey("");
      setSecretValue("");
    } catch (e) {
      const message = e instanceof Error ? e.message : "Failed to save secret";
      setSecretStatus(message);
      if (e instanceof ApiError && e.status === 403) {
        setActionAllowed(false);
      }
    }
  };

  if (auth.status === "loading" || auth.status === "unauthenticated") {
    return (
      <Card className="border-border bg-[hsl(var(--surface))]">
        <CardContent className="pt-6">
          <p className="text-sm text-muted-foreground">
            {auth.status === "loading" ? "Loading…" : "Sign in to view integration."}
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

  if (loading) {
    return (
      <Card className="border-border bg-[hsl(var(--surface))]">
        <CardContent className="pt-6">
          <p className="text-sm text-muted-foreground">Loading integration…</p>
        </CardContent>
      </Card>
    );
  }

  if (permissionRestricted) {
    return (
      <Card className="border-border bg-[hsl(var(--surface))]">
        <CardHeader>
          <CardTitle className="text-lg">Integration</CardTitle>
        </CardHeader>
        <CardContent className="pt-2">
          <p className="text-sm text-muted-foreground">
            Admin permission required to view integrations in this environment.
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

  if (error || !integration) {
    return (
      <Card className="border-border bg-[hsl(var(--surface))]">
        <CardContent className="pt-6">
          <p className="text-sm text-destructive">{error ?? "Integration not found"}</p>
          <Link href="/integrations" className="mt-2 inline-block text-sm text-primary hover:underline">
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
          {formatIntegrationType(integration.type)} integration
        </h1>
      </div>

      <Card className="border-border bg-[hsl(var(--surface))]">
        <CardHeader>
          <CardTitle className="text-lg">Configuration</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            <label className="text-sm font-medium text-foreground">Status</label>
            <select
              className="mt-1 w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
              value={status}
              onChange={(e) => setStatus(e.target.value as "active" | "inactive" | "error")}
              disabled={!canManage}
            >
              <option value="active">Active</option>
              <option value="inactive">Inactive</option>
              <option value="error">Error</option>
            </select>
          </div>
          <div>
            <label className="text-sm font-medium text-foreground">Config (JSON)</label>
            <textarea
              className="mt-1 w-full rounded-md border border-border bg-background px-3 py-2 text-xs font-mono"
              rows={10}
              value={configJson}
              onChange={(e) => setConfigJson(e.target.value)}
              disabled={!canManage}
            />
          </div>
          {saveError && <p className="text-sm text-destructive">{saveError}</p>}
          <div className="flex gap-2">
            <Button variant="primary" size="sm" onClick={handleSave} disabled={!canManage || saveLoading}>
              {saveLoading ? "Saving…" : "Save"}
            </Button>
            {!canManage && (
              <span className="text-xs text-muted-foreground">Admin permission required.</span>
            )}
          </div>
        </CardContent>
      </Card>

      <Card className="border-border bg-[hsl(var(--surface))]">
        <CardHeader>
          <CardTitle className="text-lg">Secrets</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="grid gap-3 md:grid-cols-2">
            <div>
              <label className="text-sm font-medium text-foreground">Key</label>
              <input
                className="mt-1 w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
                value={secretKey}
                onChange={(e) => setSecretKey(e.target.value)}
                disabled={!canManage}
              />
            </div>
            <div>
              <label className="text-sm font-medium text-foreground">Value</label>
              <input
                className="mt-1 w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
                value={secretValue}
                onChange={(e) => setSecretValue(e.target.value)}
                disabled={!canManage}
              />
            </div>
          </div>
          <Button variant="secondary" size="sm" onClick={handleSetSecret} disabled={!canManage}>
            Save secret
          </Button>
          {secretStatus && <p className="text-sm text-muted-foreground">{secretStatus}</p>}
        </CardContent>
      </Card>
    </div>
  );
}
