"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/lib/use-auth";
import { fetchDocuments, fetchSources, updateSource } from "@/lib/rag-api";
import { fetchOrgMembers } from "@/lib/org-api";
import type { RagSource, RagDocument } from "@/lib/rag-api";

export default function SourceDetailPage() {
  const params = useParams();
  const sourceId = params?.id as string;
  const auth = useAuth();
  const [source, setSource] = useState<RagSource | null>(null);
  const [documents, setDocuments] = useState<RagDocument[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isAdmin, setIsAdmin] = useState(false);
  const [title, setTitle] = useState("");
  const [metadataRaw, setMetadataRaw] = useState("");

  useEffect(() => {
    if (auth.status !== "authenticated" || auth.orgId == null) return;
    let cancelled = false;
    fetchOrgMembers(auth.token)
      .then((data) => {
        if (cancelled) return;
        const me = data.members.find((m) => m.user_id === auth.userId);
        setIsAdmin(me?.role === "admin");
      })
      .catch(() => setIsAdmin(false));
    return () => {
      cancelled = true;
    };
  }, [auth.status, auth.token, auth.orgId, auth.userId]);

  useEffect(() => {
    if (auth.status !== "authenticated" || auth.orgId == null) {
      setLoading(false);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError(null);
    fetchSources(auth.token)
      .then((data) => {
        if (cancelled) return;
        const found = data.sources.find((s) => s.id === sourceId);
        if (!found) {
          setError("Source not found");
          return;
        }
        setSource(found);
        setTitle(found.title);
        setMetadataRaw(found.metadata ? JSON.stringify(found.metadata, null, 2) : "");
        return fetchDocuments(auth.token, sourceId);
      })
      .then((docs) => {
        if (!docs || cancelled) return;
        setDocuments(docs.documents);
      })
      .catch((e) => {
        if (!cancelled) setError(e.message ?? "Failed to load");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [auth.status, auth.token, auth.orgId, sourceId]);

  function parseMetadata() {
    if (!metadataRaw.trim()) return undefined;
    return JSON.parse(metadataRaw);
  }

  async function onSave() {
    if (!source) return;
    setError(null);
    if (!isAdmin) {
      setError("Admin permission required to edit sources");
      return;
    }
    try {
      setSaving(true);
      const metadata = parseMetadata();
      const updated = await updateSource(auth.token, source.id, {
        title: title.trim(),
        metadata,
      });
      setSource(updated);
    } catch (e) {
      setError((e as Error).message ?? "Failed to update source");
    } finally {
      setSaving(false);
    }
  }

  if (auth.status === "loading" || auth.status === "unauthenticated") {
    return (
      <Card className="border-border bg-[hsl(var(--surface))]">
        <CardHeader>
          <CardTitle className="text-lg">Source</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">
            {auth.status === "loading" ? "Loading…" : "Sign in to view source."}
          </p>
        </CardContent>
      </Card>
    );
  }

  if (loading) {
    return (
      <Card className="border-border bg-[hsl(var(--surface))]">
        <CardContent className="pt-6">
          <p className="text-sm text-muted-foreground">Loading…</p>
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

  if (!source) return null;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-semibold tracking-tight text-foreground">
          {source.title}
        </h1>
        <Link href={`/rag/ingest?source_id=${source.id}`} passHref legacyBehavior>
          <Button variant="primary" size="md" asChild disabled={!isAdmin}>
            <a>Ingest Document</a>
          </Button>
        </Link>
      </div>

      {!isAdmin && (
        <Card className="border-border bg-[hsl(var(--surface))]">
          <CardContent className="pt-6">
            <p className="text-sm text-muted-foreground">
              Admin permission required to modify sources or ingest content.
            </p>
          </CardContent>
        </Card>
      )}

      <Card className="border-border bg-[hsl(var(--surface))]">
        <CardHeader>
          <CardTitle className="text-lg">Source Details</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            <label className="text-sm font-medium text-foreground">Title</label>
            <input
              className="mt-1 w-full rounded-[12px] border border-border bg-background px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              disabled={!isAdmin}
            />
          </div>
          <div>
            <label className="text-sm font-medium text-foreground">Metadata (JSON)</label>
            <textarea
              className="mt-1 w-full rounded-[12px] border border-border bg-background px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              rows={5}
              value={metadataRaw}
              onChange={(e) => setMetadataRaw(e.target.value)}
              disabled={!isAdmin}
            />
          </div>
          {error && <p className="text-sm text-destructive">{error}</p>}
          <Button variant="primary" size="md" onClick={onSave} disabled={!isAdmin || saving}>
            {saving ? "Saving…" : "Save"}
          </Button>
        </CardContent>
      </Card>

      <Card className="border-border bg-[hsl(var(--surface))]">
        <CardHeader>
          <CardTitle className="text-lg">Documents</CardTitle>
        </CardHeader>
        <CardContent>
          {documents.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              No documents yet. Ingest content to populate this source.
            </p>
          ) : (
            <table className="w-full text-left text-sm border-collapse">
              <thead>
                <tr className="border-b border-border">
                  <th className="py-2 pr-4 font-medium text-foreground">Title</th>
                  <th className="py-2 pr-4 font-medium text-foreground">External ID</th>
                  <th className="py-2 font-medium text-foreground">Updated</th>
                </tr>
              </thead>
              <tbody>
                {documents.map((d) => (
                  <tr key={d.id} className="border-b border-border hover:bg-muted/50">
                    <td className="py-3 pr-4">
                      <Link
                        href={`/rag/documents/${d.id}`}
                        className="text-primary hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring rounded-sm"
                      >
                        {d.title || "Untitled"}
                      </Link>
                    </td>
                    <td className="py-3 pr-4 text-muted-foreground">
                      {d.external_id || "—"}
                    </td>
                    <td className="py-3 text-muted-foreground">
                      {new Date(d.updated_at).toLocaleString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
