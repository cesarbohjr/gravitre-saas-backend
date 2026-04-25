"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/lib/use-auth";
import { postIngest, type IngestResult } from "@/lib/rag-api";
import { fetchOrgMembers } from "@/lib/org-api";

type Mode = "text" | "chunks";

export default function IngestPage() {
  const auth = useAuth();
  const params = useSearchParams();
  const sourceId = params.get("source_id") || "";
  const [mode, setMode] = useState<Mode>("text");
  const [title, setTitle] = useState("");
  const [externalId, setExternalId] = useState("");
  const [metadataRaw, setMetadataRaw] = useState("");
  const [text, setText] = useState("");
  const [chunksRaw, setChunksRaw] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [result, setResult] = useState<IngestResult | null>(null);
  const [isAdmin, setIsAdmin] = useState(false);
  const [adminLoading, setAdminLoading] = useState(true);

  useEffect(() => {
    if (auth.status !== "authenticated" || auth.orgId == null) {
      setAdminLoading(false);
      return;
    }
    let cancelled = false;
    fetchOrgMembers(auth.token)
      .then((data) => {
        if (cancelled) return;
        const me = data.members.find((m) => m.user_id === auth.userId);
        setIsAdmin(me?.role === "admin");
      })
      .catch(() => setIsAdmin(false))
      .finally(() => {
        if (!cancelled) setAdminLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [auth.status, auth.token, auth.orgId, auth.userId]);

  const disabledMessage = useMemo(() => {
    if (adminLoading) return "Checking permissions…";
    if (!isAdmin) return "Admin permission required to modify sources or ingest content.";
    return "";
  }, [adminLoading, isAdmin]);

  function parseMetadata() {
    if (!metadataRaw.trim()) return undefined;
    return JSON.parse(metadataRaw);
  }

  function parseChunks() {
    if (!chunksRaw.trim()) return [];
    const parsed = JSON.parse(chunksRaw);
    if (!Array.isArray(parsed) || !parsed.every((c) => typeof c === "string")) {
      throw new Error("Chunks JSON must be an array of strings");
    }
    return parsed;
  }

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setResult(null);
    if (!sourceId) {
      setError("source_id is required");
      return;
    }
    if (!isAdmin) {
      setError("Admin permission required to ingest content");
      return;
    }
    try {
      setSaving(true);
      const metadata = parseMetadata();
      const payload: Record<string, unknown> = {
        source_id: sourceId,
        external_id: externalId.trim() || undefined,
        title: title.trim() || undefined,
        metadata,
      };
      if (mode === "text") {
        if (!text.trim()) throw new Error("Text is required");
        payload.text = text;
      } else {
        const chunks = parseChunks();
        if (chunks.length === 0) throw new Error("Chunks array is required");
        payload.chunks = chunks;
      }
      const res = await postIngest(auth.token, payload);
      setResult(res);
    } catch (e) {
      setError((e as Error).message ?? "Failed to ingest");
    } finally {
      setSaving(false);
    }
  }

  if (auth.status === "loading" || auth.status === "unauthenticated") {
    return (
      <Card className="border-border bg-[hsl(var(--surface))]">
        <CardHeader>
          <CardTitle className="text-lg">Ingest Document</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">
            {auth.status === "loading" ? "Loading…" : "Sign in to ingest content."}
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      <Card className="border-border bg-[hsl(var(--surface))]">
        <CardHeader>
          <CardTitle className="text-lg">Ingest Document</CardTitle>
        </CardHeader>
        <CardContent>
          {!isAdmin && (
            <p className="mb-4 text-sm text-muted-foreground">{disabledMessage}</p>
          )}
          <form className="space-y-4" onSubmit={onSubmit}>
            <div>
              <label className="text-sm font-medium text-foreground">Source ID</label>
              <input
                className="mt-1 w-full rounded-[12px] border border-border bg-background px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                value={sourceId}
                disabled
              />
            </div>
            <div className="flex gap-2">
              <Button type="button" variant={mode === "text" ? "primary" : "secondary"} size="sm" onClick={() => setMode("text")}>
                Text Mode
              </Button>
              <Button type="button" variant={mode === "chunks" ? "primary" : "secondary"} size="sm" onClick={() => setMode("chunks")}>
                Chunks JSON
              </Button>
            </div>
            <div>
              <label className="text-sm font-medium text-foreground">Title (optional)</label>
              <input
                className="mt-1 w-full rounded-[12px] border border-border bg-background px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
              />
            </div>
            <div>
              <label className="text-sm font-medium text-foreground">External ID (optional)</label>
              <input
                className="mt-1 w-full rounded-[12px] border border-border bg-background px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                value={externalId}
                onChange={(e) => setExternalId(e.target.value)}
              />
            </div>
            <div>
              <label className="text-sm font-medium text-foreground">Metadata (optional JSON)</label>
              <textarea
                className="mt-1 w-full rounded-[12px] border border-border bg-background px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                rows={4}
                value={metadataRaw}
                onChange={(e) => setMetadataRaw(e.target.value)}
              />
            </div>
            {mode === "text" ? (
              <div>
                <label className="text-sm font-medium text-foreground">Text</label>
                <textarea
                  className="mt-1 w-full rounded-[12px] border border-border bg-background px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  rows={10}
                  value={text}
                  onChange={(e) => setText(e.target.value)}
                  placeholder="Paste document text here"
                />
              </div>
            ) : (
              <div>
                <label className="text-sm font-medium text-foreground">Chunks (JSON array)</label>
                <textarea
                  className="mt-1 w-full rounded-[12px] border border-border bg-background px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  rows={10}
                  value={chunksRaw}
                  onChange={(e) => setChunksRaw(e.target.value)}
                  placeholder='["chunk one","chunk two"]'
                />
              </div>
            )}
            {error && <p className="text-sm text-destructive">{error}</p>}
            <Button type="submit" variant="primary" size="md" disabled={saving || !isAdmin}>
              {saving ? "Ingesting…" : "Ingest"}
            </Button>
          </form>
        </CardContent>
      </Card>

      {result && (
        <Card className="border-border bg-[hsl(var(--surface))]">
          <CardHeader>
            <CardTitle className="text-lg">Ingest Summary</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm">
            <div>Status: {result.status}</div>
            {result.document_id && <div>Document ID: {result.document_id}</div>}
            {typeof result.chunk_count === "number" && <div>Chunk count: {result.chunk_count}</div>}
            {result.ingest_id && (
              <div>
                Ingest job:{" "}
                <Link
                  href={`/rag/ingest/${result.ingest_id}`}
                  className="text-primary hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring rounded-sm"
                >
                  {result.ingest_id}
                </Link>
              </div>
            )}
            {result.document_id && result.status === "completed" && (
              <div>
                Document:{" "}
                <Link
                  href={`/rag/documents/${result.document_id}`}
                  className="text-primary hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring rounded-sm"
                >
                  View document
                </Link>
              </div>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
}
