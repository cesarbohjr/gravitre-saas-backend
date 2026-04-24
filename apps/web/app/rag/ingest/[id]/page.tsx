"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/lib/use-auth";
import { fetchIngestJob, type IngestJob } from "@/lib/rag-api";

export default function IngestStatusPage() {
  const auth = useAuth();
  const params = useParams();
  const ingestId = params?.id as string;
  const [job, setJob] = useState<IngestJob | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = () => {
    if (auth.status !== "authenticated") return;
    setLoading(true);
    setError(null);
    fetchIngestJob(auth.token, ingestId)
      .then((data) => setJob(data))
      .catch((e) => setError(e.message ?? "Failed to load"))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    if (auth.status !== "authenticated") return;
    load();
  }, [auth.status, auth.token, ingestId]);

  useEffect(() => {
    if (!job) return;
    if (job.status !== "queued" && job.status !== "running") return;
    const id = setInterval(() => load(), 4000);
    return () => clearInterval(id);
  }, [job?.status, auth.status, auth.token, ingestId]);

  if (auth.status === "loading" || auth.status === "unauthenticated") {
    return (
      <Card className="border-border bg-[hsl(var(--surface))]">
        <CardHeader>
          <CardTitle className="text-lg">Ingest Status</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">
            {auth.status === "loading" ? "Loading…" : "Sign in to view ingest status."}
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="border-border bg-[hsl(var(--surface))]">
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle className="text-lg">Ingest Status</CardTitle>
        <Button variant="secondary" size="sm" onClick={load} disabled={loading}>
          Refresh
        </Button>
      </CardHeader>
      <CardContent>
        {loading ? (
          <p className="text-sm text-muted-foreground">Loading…</p>
        ) : error ? (
          <p className="text-sm text-destructive">{error}</p>
        ) : job ? (
          <div className="space-y-2 text-sm">
            <div>Status: {job.status}</div>
            <div>Chunk count: {job.chunk_count}</div>
            {job.error_code && <div className="text-destructive">Error: {job.error_code}</div>}
            {job.started_at && <div>Started: {new Date(job.started_at).toLocaleString()}</div>}
            {job.completed_at && (
              <div>Completed: {new Date(job.completed_at).toLocaleString()}</div>
            )}
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">No ingest job found.</p>
        )}
      </CardContent>
    </Card>
  );
}
