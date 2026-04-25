"use client";

import { Fragment, useCallback, useEffect, useMemo, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { getEnvironmentHeader } from "@/lib/environment";
import { useAuth } from "@/lib/use-auth";
import {
  fetchAuditLog,
  getActionLabel,
  type AuditItem,
} from "@/lib/audit-api";

const ACTION_OPTIONS = [
  { value: "all", label: "All actions" },
  { value: "workflow.dry_run", label: "Dry run" },
  { value: "workflow.execute", label: "Execute" },
  { value: "slack.send", label: "Slack" },
  { value: "email.send", label: "Email" },
  { value: "webhook.send", label: "Webhook" },
];

const RESOURCE_OPTIONS = [
  { value: "all", label: "All resources" },
  { value: "workflow_run", label: "Workflow run" },
  { value: "workflow", label: "Workflow" },
  { value: "connector", label: "Integration" },
  { value: "operator", label: "Operator" },
];

const TIME_RANGE_OPTIONS = [
  { value: "24h", label: "Last 24h" },
  { value: "7d", label: "Last 7 days" },
  { value: "30d", label: "Last 30 days" },
  { value: "90d", label: "Last 90 days" },
  { value: "all", label: "All time" },
];

function getRangeStart(range: string): string | null {
  const now = Date.now();
  const toIso = (value: number) => new Date(value).toISOString();
  switch (range) {
    case "24h":
      return toIso(now - 24 * 60 * 60 * 1000);
    case "7d":
      return toIso(now - 7 * 24 * 60 * 60 * 1000);
    case "30d":
      return toIso(now - 30 * 24 * 60 * 60 * 1000);
    case "90d":
      return toIso(now - 90 * 24 * 60 * 60 * 1000);
    default:
      return null;
  }
}

function getSeverity(action: string): "Info" | "Medium" | "High" {
  const normalized = action.toLowerCase();
  if (normalized.includes("failed") || normalized.includes("rejected")) return "High";
  if (normalized.includes("pending") || normalized.includes("approval")) return "Medium";
  return "Info";
}

function SeverityBadge({ action }: { action: string }) {
  const severity = getSeverity(action);
  return (
    <span className="inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-medium bg-muted text-muted-foreground border-border">
      {severity}
    </span>
  );
}

export default function AuditPage() {
  const auth = useAuth();
  const environment = getEnvironmentHeader();
  const [items, setItems] = useState<AuditItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionFilter, setActionFilter] = useState("all");
  const [actorFilter, setActorFilter] = useState("");
  const [resourceFilter, setResourceFilter] = useState("all");
  const [timeRange, setTimeRange] = useState("30d");
  const [search, setSearch] = useState("");
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [pageIndex, setPageIndex] = useState(0);
  const [pageCursors, setPageCursors] = useState<Array<string | null>>([null]);
  const [nextCursor, setNextCursor] = useState<string | null>(null);

  const loadAudit = useCallback(
    (cursor: string | null, page: number) => {
      if (auth.status !== "authenticated" || auth.orgId == null) {
        setLoading(false);
        return;
      }
      setLoading(true);
      setError(null);
      const actionPrefix = actionFilter !== "all" ? actionFilter : null;
      const resourceType = resourceFilter !== "all" ? resourceFilter : null;
      const startAt = getRangeStart(timeRange);
      fetchAuditLog(auth.token, {
        cursor,
        limit: 50,
        action_prefix: actionPrefix,
        actor_id: actorFilter.trim() || null,
        resource_type: resourceType,
        start_at: startAt,
      })
        .then((res) => {
          setItems(res.items);
          setNextCursor(res.next_cursor ?? null);
          setPageIndex(page);
        })
        .catch((e) => setError(e.message ?? "Failed to load audit events."))
        .finally(() => setLoading(false));
    },
    [auth.status, auth.token, auth.orgId, actionFilter, actorFilter, resourceFilter, timeRange]
  );

  useEffect(() => {
    setPageCursors([null]);
    loadAudit(null, 0);
  }, [loadAudit]);

  const filteredItems = useMemo(() => {
    const trimmedSearch = search.trim().toLowerCase();
    if (!trimmedSearch) return items;
    return items.filter((item) => {
      return (
        item.action.toLowerCase().includes(trimmedSearch) ||
        item.actor_id.toLowerCase().includes(trimmedSearch) ||
        item.resource_type.toLowerCase().includes(trimmedSearch) ||
        item.resource_id.toLowerCase().includes(trimmedSearch)
      );
    });
  }, [items, search]);

  const handleNext = () => {
    if (!nextCursor) return;
    const nextPage = pageIndex + 1;
    setPageCursors((prev) => {
      const copy = [...prev];
      copy[nextPage] = nextCursor;
      return copy;
    });
    loadAudit(nextCursor, nextPage);
  };

  const handlePrev = () => {
    if (pageIndex === 0) return;
    const prevPage = pageIndex - 1;
    const prevCursor = pageCursors[prevPage] ?? null;
    loadAudit(prevCursor, prevPage);
  };

  if (auth.status === "loading" || auth.status === "unauthenticated") {
    return (
      <Card className="border-border bg-[hsl(var(--surface))]">
        <CardHeader>
          <CardTitle className="text-lg">Audit</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">
            {auth.status === "loading" ? "Loading…" : "Sign in to view audit events."}
          </p>
        </CardContent>
      </Card>
    );
  }

  if (auth.orgId == null) {
    return (
      <Card className="border-border bg-[hsl(var(--surface))]">
        <CardHeader>
          <CardTitle className="text-lg">Audit</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">
            Onboarding pending. Contact admin for org access to view audit events.
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-semibold tracking-tight text-foreground">Audit</h1>
        <p className="text-sm text-muted-foreground">
          Environment: <span className="font-medium text-foreground">{environment}</span>
        </p>
      </div>

      <Card className="border-border bg-[hsl(var(--surface))]">
        <CardHeader>
          <CardTitle className="text-lg">Audit log</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-5">
            <div className="space-y-1">
              <label className="text-xs font-medium text-muted-foreground" htmlFor="audit-range">
                Date range
              </label>
              <select
                id="audit-range"
                value={timeRange}
                onChange={(event) => setTimeRange(event.target.value)}
                className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              >
                {TIME_RANGE_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </div>
            <div className="space-y-1">
              <label className="text-xs font-medium text-muted-foreground" htmlFor="audit-action">
                Action type
              </label>
              <select
                id="audit-action"
                value={actionFilter}
                onChange={(event) => setActionFilter(event.target.value)}
                className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              >
                {ACTION_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </div>
            <div className="space-y-1">
              <label className="text-xs font-medium text-muted-foreground" htmlFor="audit-actor">
                Actor
              </label>
              <input
                id="audit-actor"
                value={actorFilter}
                onChange={(event) => setActorFilter(event.target.value)}
                placeholder="User ID"
                className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              />
            </div>
            <div className="space-y-1">
              <label className="text-xs font-medium text-muted-foreground" htmlFor="audit-resource">
                Resource type
              </label>
              <select
                id="audit-resource"
                value={resourceFilter}
                onChange={(event) => setResourceFilter(event.target.value)}
                className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              >
                {RESOURCE_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </div>
            <div className="space-y-1 xl:col-span-1 md:col-span-2">
              <label className="text-xs font-medium text-muted-foreground" htmlFor="audit-search">
                Search
              </label>
              <input
                id="audit-search"
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                placeholder="Action, actor, resource"
                className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              />
            </div>
          </div>

          {error && (
            <div className="flex flex-wrap items-center justify-between gap-3 rounded-md border border-border bg-destructive/5 px-3 py-2">
              <p className="text-sm text-destructive">{error}</p>
              <Button variant="secondary" size="sm" onClick={() => loadAudit(pageCursors[pageIndex] ?? null, pageIndex)}>
                Retry
              </Button>
            </div>
          )}

          <div className="overflow-x-auto">
            <table className="w-full min-w-[900px] text-left text-sm border-collapse">
              <thead>
                <tr className="border-b border-border">
                  <th className="py-2 pr-4 font-medium text-foreground">Timestamp</th>
                  <th className="py-2 pr-4 font-medium text-foreground">Action</th>
                  <th className="py-2 pr-4 font-medium text-foreground">Actor</th>
                  <th className="py-2 pr-4 font-medium text-foreground">Resource</th>
                  <th className="py-2 pr-4 font-medium text-foreground">Environment</th>
                  <th className="py-2 font-medium text-foreground">Status</th>
                </tr>
              </thead>
              <tbody>
                {loading ? (
                  Array.from({ length: 6 }).map((_, idx) => (
                    <tr key={`skeleton-${idx}`} className="border-b border-border animate-pulse">
                      <td className="py-3 pr-4">
                        <div className="h-4 w-28 rounded bg-muted" />
                      </td>
                      <td className="py-3 pr-4">
                        <div className="h-4 w-36 rounded bg-muted" />
                      </td>
                      <td className="py-3 pr-4">
                        <div className="h-4 w-32 rounded bg-muted" />
                      </td>
                      <td className="py-3 pr-4">
                        <div className="h-4 w-28 rounded bg-muted" />
                      </td>
                      <td className="py-3 pr-4">
                        <div className="h-4 w-20 rounded bg-muted" />
                      </td>
                      <td className="py-3">
                        <div className="h-4 w-16 rounded bg-muted" />
                      </td>
                    </tr>
                  ))
                ) : filteredItems.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="py-6 text-sm text-muted-foreground">
                      No audit events found.
                    </td>
                  </tr>
                ) : (
                  filteredItems.map((item) => {
                    const expanded = expandedId === item.id;
                    const env =
                      (item.metadata?.environment as string | undefined) ?? environment;
                    return (
                      <Fragment key={item.id}>
                        <tr className="border-b border-border hover:bg-muted/50">
                          <td className="py-3 pr-4 text-muted-foreground">
                            <button
                              type="button"
                              onClick={() => setExpandedId(expanded ? null : item.id)}
                              className="text-left text-sm text-foreground hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring rounded-sm"
                            >
                              {new Date(item.created_at).toLocaleString()}
                            </button>
                          </td>
                          <td className="py-3 pr-4 text-foreground">{getActionLabel(item.action)}</td>
                          <td className="py-3 pr-4 text-muted-foreground">{item.actor_id.slice(0, 8)}…</td>
                          <td className="py-3 pr-4 text-muted-foreground">
                            {item.resource_type} · {item.resource_id.slice(0, 8)}…
                          </td>
                          <td className="py-3 pr-4 text-muted-foreground">{env}</td>
                          <td className="py-3">
                            <SeverityBadge action={item.action} />
                          </td>
                        </tr>
                        {expanded && (
                          <tr className="border-b border-border bg-muted/40">
                            <td colSpan={6} className="px-4 py-4 text-xs text-muted-foreground">
                              <div className="space-y-2">
                                <div>
                                  <span className="font-medium text-foreground">Resource ID:</span>{" "}
                                  {item.resource_id}
                                </div>
                                <div>
                                  <span className="font-medium text-foreground">Actor ID:</span>{" "}
                                  {item.actor_id}
                                </div>
                                <pre className="mt-2 overflow-auto rounded-md border border-border bg-background p-3 text-xs text-foreground">
                                  {JSON.stringify(item.metadata ?? {}, null, 2)}
                                </pre>
                              </div>
                            </td>
                          </tr>
                        )}
                      </Fragment>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>

          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="text-xs text-muted-foreground">Page {pageIndex + 1}</div>
            <div className="flex items-center gap-2">
              <Button variant="secondary" size="sm" onClick={handlePrev} disabled={pageIndex === 0 || loading}>
                Previous
              </Button>
              <Button variant="secondary" size="sm" onClick={handleNext} disabled={!nextCursor || loading}>
                Next
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
