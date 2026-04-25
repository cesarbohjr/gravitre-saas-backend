"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/lib/use-auth";
import { createSource, type RagSourceType } from "@/lib/rag-api";
import { fetchOrgMembers } from "@/lib/org-api";

const SOURCE_TYPES: RagSourceType[] = [
  "manual",
  "internal",
  "external",
  "product",
  "support",
];

export default function NewSourcePage() {
  const auth = useAuth();
  const router = useRouter();
  const [title, setTitle] = useState("");
  const [type, setType] = useState<RagSourceType | "">("");
  const [metadataRaw, setMetadataRaw] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
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
      .catch(() => {
        if (!cancelled) setIsAdmin(false);
      })
      .finally(() => {
        if (!cancelled) setAdminLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [auth.status, auth.token, auth.orgId, auth.userId]);

  function parseMetadata() {
    if (!metadataRaw.trim()) return undefined;
    try {
      return JSON.parse(metadataRaw);
    } catch {
      throw new Error("Metadata must be valid JSON");
    }
  }

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (!title.trim()) {
      setError("Title is required");
      return;
    }
    if (!type) {
      setError("Type is required");
      return;
    }
    if (!isAdmin) {
      setError("Admin permission required to create sources");
      return;
    }
    try {
      setSaving(true);
      const metadata = parseMetadata();
      const created = await createSource(auth.token, {
        title: title.trim(),
        type,
        metadata,
      });
      router.push(`/rag/sources/${created.id}`);
    } catch (e) {
      setError((e as Error).message ?? "Failed to create source");
    } finally {
      setSaving(false);
    }
  }

  if (auth.status === "loading" || auth.status === "unauthenticated") {
    return (
      <Card className="border-border bg-[hsl(var(--surface))]">
        <CardHeader>
          <CardTitle className="text-lg">New Source</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">
            {auth.status === "loading" ? "Loading…" : "Sign in to create sources."}
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="border-border bg-[hsl(var(--surface))]">
      <CardHeader>
        <CardTitle className="text-lg">Create Source</CardTitle>
      </CardHeader>
      <CardContent>
        {!isAdmin && !adminLoading && (
          <p className="mb-4 text-sm text-muted-foreground">
            Admin permission required to modify sources or ingest content.
          </p>
        )}
        <form className="space-y-4" onSubmit={onSubmit}>
          <div>
            <label className="text-sm font-medium text-foreground">Title</label>
            <input
              className="mt-1 w-full rounded-[12px] border border-border bg-background px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="e.g. Product Docs"
            />
          </div>
          <div>
            <label className="text-sm font-medium text-foreground">Type</label>
            <select
              className="mt-1 w-full rounded-[12px] border border-border bg-background px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              value={type}
              onChange={(e) => setType(e.target.value as RagSourceType)}
            >
              <option value="">Select type…</option>
              {SOURCE_TYPES.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="text-sm font-medium text-foreground">Metadata (optional JSON)</label>
            <textarea
              className="mt-1 w-full rounded-[12px] border border-border bg-background px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              rows={5}
              value={metadataRaw}
              onChange={(e) => setMetadataRaw(e.target.value)}
              placeholder='{"owner":"team-a"}'
            />
          </div>
          {error && <p className="text-sm text-destructive">{error}</p>}
          <Button type="submit" variant="primary" size="md" disabled={saving || !isAdmin}>
            {saving ? "Creating…" : "Create Source"}
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}
