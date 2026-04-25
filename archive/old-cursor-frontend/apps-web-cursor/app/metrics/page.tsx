"use client";

import { useEffect, useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/lib/use-auth";
import {
  fetchMetricsIntegrations,
  fetchMetricsOverview,
  fetchMetricsRag,
  fetchMetricsTimeseries,
  fetchMetricsWorkflows,
  type MetricsIntegrations,
  type MetricsOverview,
  type MetricsRag,
  type MetricsTimeseries,
  type MetricsWorkflows,
  type Range,
} from "@/lib/metrics-api";
import { MetricCard } from "@/components/metrics/metric-card";
import { RangeSwitcher } from "@/components/metrics/range-switcher";
import { MetricsSection } from "@/components/metrics/section";
import { EmptyState } from "@/components/metrics/empty-state";
import { ErrorState } from "@/components/metrics/error-state";
import { getEnvironmentHeader } from "@/lib/environment";

const TIMESERIES_METRICS = [
  { key: "exec_runs_total", label: "Exec runs total" },
  { key: "exec_failures_total", label: "Exec failures total" },
  { key: "rag_retrieval_total", label: "RAG retrieval total" },
  { key: "ingest_jobs_total", label: "Ingest jobs total" },
  { key: "connector_sends_total", label: "Integration sends total" },
];

function percent(value: number) {
  return `${Math.round(value * 100)}%`;
}

export default function MetricsPage() {
  const auth = useAuth();
  const [range, setRange] = useState<Range>("7d");

  const [overview, setOverview] = useState<MetricsOverview | null>(null);
  const [workflows, setWorkflows] = useState<MetricsWorkflows | null>(null);
  const [rag, setRag] = useState<MetricsRag | null>(null);
  const [integrations, setIntegrations] = useState<MetricsIntegrations | null>(null);
  const [timeseries, setTimeseries] = useState<MetricsTimeseries | null>(null);
  const [timeseriesMetric, setTimeseriesMetric] = useState(TIMESERIES_METRICS[0].key);
  const environment = getEnvironmentHeader();

  const [overviewLoading, setOverviewLoading] = useState(false);
  const [workflowsLoading, setWorkflowsLoading] = useState(false);
  const [ragLoading, setRagLoading] = useState(false);
  const [integrationsLoading, setIntegrationsLoading] = useState(false);
  const [timeseriesLoading, setTimeseriesLoading] = useState(false);

  const [overviewError, setOverviewError] = useState<string | null>(null);
  const [workflowsError, setWorkflowsError] = useState<string | null>(null);
  const [ragError, setRagError] = useState<string | null>(null);
  const [integrationsError, setIntegrationsError] = useState<string | null>(null);
  const [timeseriesError, setTimeseriesError] = useState<string | null>(null);

  const canFetch = auth.status === "authenticated" && auth.orgId != null;

  const loadOverview = () => {
    if (!canFetch) return;
    setOverviewLoading(true);
    setOverviewError(null);
    fetchMetricsOverview(auth.token, range)
      .then(setOverview)
      .catch((e) => setOverviewError(e.message ?? "Metrics temporarily unavailable."))
      .finally(() => setOverviewLoading(false));
  };

  const loadWorkflows = () => {
    if (!canFetch) return;
    setWorkflowsLoading(true);
    setWorkflowsError(null);
    fetchMetricsWorkflows(auth.token, range)
      .then(setWorkflows)
      .catch((e) => setWorkflowsError(e.message ?? "Metrics temporarily unavailable."))
      .finally(() => setWorkflowsLoading(false));
  };

  const loadRag = () => {
    if (!canFetch) return;
    setRagLoading(true);
    setRagError(null);
    fetchMetricsRag(auth.token, range)
      .then(setRag)
      .catch((e) => setRagError(e.message ?? "Metrics temporarily unavailable."))
      .finally(() => setRagLoading(false));
  };

  const loadIntegrations = () => {
    if (!canFetch) return;
    setIntegrationsLoading(true);
    setIntegrationsError(null);
    fetchMetricsIntegrations(auth.token, range)
      .then(setIntegrations)
      .catch((e) => setIntegrationsError(e.message ?? "Metrics temporarily unavailable."))
      .finally(() => setIntegrationsLoading(false));
  };

  const loadTimeseries = () => {
    if (!canFetch) return;
    setTimeseriesLoading(true);
    setTimeseriesError(null);
    fetchMetricsTimeseries(auth.token, range, timeseriesMetric)
      .then(setTimeseries)
      .catch((e) => setTimeseriesError(e.message ?? "Metrics temporarily unavailable."))
      .finally(() => setTimeseriesLoading(false));
  };

  useEffect(() => {
    if (!canFetch) return;
    loadOverview();
    loadWorkflows();
    loadRag();
    loadIntegrations();
    loadTimeseries();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [range, auth.status, auth.orgId]);

  useEffect(() => {
    if (!canFetch) return;
    loadTimeseries();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [timeseriesMetric]);

  if (auth.status === "loading" || auth.status === "unauthenticated") {
    return (
      <Card className="border-border bg-[hsl(var(--surface))]">
        <CardContent className="pt-6">
          <p className="text-sm text-muted-foreground">
            {auth.status === "loading" ? "Loading…" : "Sign in to view metrics."}
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
            Onboarding pending — contact admin for org access.
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-semibold tracking-tight text-foreground">Metrics</h1>
          <p className="text-sm text-muted-foreground">
            Environment: <span className="font-medium text-foreground">{environment}</span>
          </p>
        </div>
        <RangeSwitcher value={range} onChange={setRange} />
      </div>

      <MetricsSection
        title="Overview"
        actions={<Button size="sm" variant="secondary" onClick={loadOverview} disabled={overviewLoading}>Retry</Button>}
      >
        {overviewLoading ? (
          <EmptyState message="Loading overview…" />
        ) : overviewError ? (
          <ErrorState message={overviewError} onRetry={loadOverview} />
        ) : overview ? (
          <div className="grid gap-4 md:grid-cols-3">
            <MetricCard label="Dry runs total" value={overview.workflows.dry_runs_total} />
            <MetricCard label="Exec runs total" value={overview.workflows.exec_runs_total} />
            <MetricCard label="Exec success rate" value={percent(overview.workflows.exec_success_rate)} tone="success" />
            <MetricCard label="Pending approvals" value={overview.workflows.pending_approvals} tone="warning" />
            <MetricCard label="RAG requests total" value={overview.rag.retrieval_requests_total} />
            <MetricCard label="Avg RAG latency (ms)" value={Math.round(overview.rag.avg_latency_ms)} />
            <MetricCard label="Ingest jobs total" value={overview.ingestion.ingest_jobs_total} />
            <MetricCard label="Ingest success rate" value={percent(overview.ingestion.ingest_success_rate)} tone="success" />
            <MetricCard label="Integration sends total" value={overview.connectors.slack_sent + overview.connectors.email_sent + overview.connectors.webhook_sent} />
            <MetricCard label="Send failures total" value={overview.connectors.send_failures_total} tone="destructive" />
          </div>
        ) : (
          <EmptyState message="No metrics available yet." />
        )}
      </MetricsSection>

      <MetricsSection
        title="Workflows"
        actions={<Button size="sm" variant="secondary" onClick={loadWorkflows} disabled={workflowsLoading}>Retry</Button>}
      >
        {workflowsLoading ? (
          <EmptyState message="Loading workflow metrics…" />
        ) : workflowsError ? (
          <ErrorState message={workflowsError} onRetry={loadWorkflows} />
        ) : workflows ? (
          <div className="space-y-6">
            <div className="grid gap-4 md:grid-cols-3">
              <MetricCard label="Avg exec duration (ms)" value={Math.round(workflows.exec.avg_duration_ms)} />
              <MetricCard label="P95 exec duration (ms)" value={Math.round(workflows.exec.p95_duration_ms)} subtext={workflows.exec.p95_duration_ms ? "" : "p95 unavailable"} />
              <MetricCard label="Dry runs total" value={workflows.dry_run.total} />
            </div>

            <div>
              <div className="text-sm font-medium text-foreground mb-2">Status breakdown</div>
              <table className="w-full text-left text-sm border-collapse">
                <thead>
                  <tr className="border-b border-border">
                    <th className="py-2 pr-4 font-medium text-foreground">Status</th>
                    <th className="py-2 font-medium text-foreground">Count</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(workflows.exec.by_status).map(([status, count]) => (
                    <tr key={status} className="border-b border-border">
                      <td className="py-2 pr-4 text-muted-foreground">{status}</td>
                      <td className="py-2">{count}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div>
              <div className="text-sm font-medium text-foreground mb-2">Approval funnel</div>
              <table className="w-full text-left text-sm border-collapse">
                <thead>
                  <tr className="border-b border-border">
                    <th className="py-2 pr-4 font-medium text-foreground">Stage</th>
                    <th className="py-2 font-medium text-foreground">Count</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(workflows.exec.approval_funnel).map(([stage, count]) => (
                    <tr key={stage} className="border-b border-border">
                      <td className="py-2 pr-4 text-muted-foreground">{stage}</td>
                      <td className="py-2">{count}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div>
              <div className="text-sm font-medium text-foreground mb-2">Step failures by type</div>
              {Object.keys(workflows.exec.step_failures_by_type).length === 0 ? (
                <EmptyState message="No step failures recorded." />
              ) : (
                <table className="w-full text-left text-sm border-collapse">
                  <thead>
                    <tr className="border-b border-border">
                      <th className="py-2 pr-4 font-medium text-foreground">Step type</th>
                      <th className="py-2 font-medium text-foreground">Failures</th>
                    </tr>
                  </thead>
                  <tbody>
                    {Object.entries(workflows.exec.step_failures_by_type).map(([stepType, count]) => (
                      <tr key={stepType} className="border-b border-border">
                        <td className="py-2 pr-4 text-muted-foreground">{stepType}</td>
                        <td className="py-2">{count}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </div>
        ) : (
          <EmptyState message="No workflow metrics yet." />
        )}
      </MetricsSection>

      <MetricsSection
        title="RAG"
        actions={<Button size="sm" variant="secondary" onClick={loadRag} disabled={ragLoading}>Retry</Button>}
      >
        {ragLoading ? (
          <EmptyState message="Loading RAG metrics…" />
        ) : ragError ? (
          <ErrorState message={ragError} onRetry={loadRag} />
        ) : rag ? (
          <div className="space-y-6">
            {rag.retrieval.insufficient_data && (
              <Card className="border-border bg-[hsl(var(--surface-2))]">
                <CardContent className="pt-4">
                  <p className="text-sm text-muted-foreground">
                    Not enough retrieval log data yet — metrics will appear as usage grows.
                  </p>
                </CardContent>
              </Card>
            )}
            <div className="grid gap-4 md:grid-cols-3">
              <MetricCard label="Retrieval total" value={rag.retrieval.total} />
              <MetricCard label="Avg latency (ms)" value={Math.round(rag.retrieval.avg_latency_ms)} />
              <MetricCard label="P95 latency (ms)" value={Math.round(rag.retrieval.p95_latency_ms)} subtext={rag.retrieval.p95_latency_ms ? "" : "p95 unavailable"} />
              <MetricCard label="Avg result count" value={Math.round(rag.retrieval.avg_result_count)} />
              <MetricCard label="Zero-result rate" value={percent(rag.retrieval.zero_result_rate)} tone="warning" />
            </div>

            <div>
              <div className="text-sm font-medium text-foreground mb-2">Ingestion status</div>
              <table className="w-full text-left text-sm border-collapse">
                <thead>
                  <tr className="border-b border-border">
                    <th className="py-2 pr-4 font-medium text-foreground">Status</th>
                    <th className="py-2 font-medium text-foreground">Count</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(rag.ingestion.by_status).map(([status, count]) => (
                    <tr key={status} className="border-b border-border">
                      <td className="py-2 pr-4 text-muted-foreground">{status}</td>
                      <td className="py-2">{count}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="grid gap-4 md:grid-cols-2">
              <MetricCard label="Avg chunks/job" value={Math.round(rag.ingestion.avg_chunks_per_job)} />
              <MetricCard label="P95 chunks/job" value={Math.round(rag.ingestion.p95_chunks_per_job)} subtext={rag.ingestion.p95_chunks_per_job ? "" : "p95 unavailable"} />
            </div>
          </div>
        ) : (
          <EmptyState message="No RAG metrics yet." />
        )}
      </MetricsSection>

      <MetricsSection
        title="Integrations & Ingestion"
        actions={<Button size="sm" variant="secondary" onClick={loadIntegrations} disabled={integrationsLoading}>Retry</Button>}
      >
        {integrationsLoading ? (
          <EmptyState message="Loading integration metrics…" />
        ) : integrationsError ? (
          <ErrorState message={integrationsError} onRetry={loadIntegrations} />
        ) : integrations && overview ? (
          <div className="space-y-6">
            <table className="w-full text-left text-sm border-collapse">
              <thead>
                <tr className="border-b border-border">
                  <th className="py-2 pr-4 font-medium text-foreground">Integration</th>
                  <th className="py-2 pr-4 font-medium text-foreground">Sent</th>
                  <th className="py-2 font-medium text-foreground">Failed</th>
                </tr>
              </thead>
              <tbody>
                <tr className="border-b border-border">
                  <td className="py-2 pr-4 text-muted-foreground">Slack</td>
                  <td className="py-2">{integrations.slack.sent}</td>
                  <td className="py-2">{integrations.slack.failed}</td>
                </tr>
                <tr className="border-b border-border">
                  <td className="py-2 pr-4 text-muted-foreground">Email</td>
                  <td className="py-2">{integrations.email.sent}</td>
                  <td className="py-2">{integrations.email.failed}</td>
                </tr>
                <tr className="border-b border-border">
                  <td className="py-2 pr-4 text-muted-foreground">Webhook</td>
                  <td className="py-2">{integrations.webhook.sent}</td>
                  <td className="py-2">{integrations.webhook.failed}</td>
                </tr>
              </tbody>
            </table>

            <div className="grid gap-4 md:grid-cols-3">
              <MetricCard label="Ingest jobs total" value={overview.ingestion.ingest_jobs_total} />
              <MetricCard label="Ingest success rate" value={percent(overview.ingestion.ingest_success_rate)} tone="success" />
              <MetricCard label="Chunks embedded total" value={overview.ingestion.chunks_embedded_total} />
            </div>
          </div>
        ) : (
          <EmptyState message="No integration metrics yet." />
        )}
      </MetricsSection>

      <MetricsSection
        title="Trend"
        actions={
          <div className="flex items-center gap-2">
            <select
              className="rounded-[12px] border border-border bg-background px-2 py-1 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              value={timeseriesMetric}
              onChange={(e) => setTimeseriesMetric(e.target.value)}
            >
              {TIMESERIES_METRICS.map((m) => (
                <option key={m.key} value={m.key}>
                  {m.label}
                </option>
              ))}
            </select>
            <Button size="sm" variant="secondary" onClick={loadTimeseries} disabled={timeseriesLoading}>
              Retry
            </Button>
          </div>
        }
      >
        {timeseriesLoading ? (
          <EmptyState message="Loading trend…" />
        ) : timeseriesError ? (
          <ErrorState message={timeseriesError} onRetry={loadTimeseries} />
        ) : timeseries ? (
          timeseries.points.length === 0 ? (
            <EmptyState message="No trend data yet." />
          ) : (
            <table className="w-full text-left text-sm border-collapse">
              <thead>
                <tr className="border-b border-border">
                  <th className="py-2 pr-4 font-medium text-foreground">Date</th>
                  <th className="py-2 font-medium text-foreground">Value</th>
                </tr>
              </thead>
              <tbody>
                {timeseries.points.map((p) => (
                  <tr key={p.date} className="border-b border-border">
                    <td className="py-2 pr-4 text-muted-foreground">{p.date}</td>
                    <td className="py-2">{p.value}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )
        ) : (
          <EmptyState message="Trend data unavailable." />
        )}
      </MetricsSection>
    </div>
  );
}
