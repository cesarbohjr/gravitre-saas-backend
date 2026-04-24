"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/lib/use-auth";
import { fetchDocument, type RagDocument } from "@/lib/rag-api";
import { fetchOrgMembers } from "@/lib/org-api";

type RagChunk = NonNullable<RagDocument["chunks"]>[number];

export default function DocumentDetailPage() {
  const auth = useAuth();
  const params = useParams();
  const docId = params?.id as string;
  const token = auth.status === "authenticated" ? auth.token : "";
  const userId = auth.status === "authenticated" ? auth.userId : "";
  const [doc, setDoc] = useState<RagDocument | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isAdmin, setIsAdmin] = useState(false);
  const [showChunks, setShowChunks] = useState(false);

  useEffect(() => {
    if (!token) {
      setIsAdmin(false);
      return;
    }
    fetchOrgMembers(token)
      .then((data) => {
        const me = data.members.find((m) => m.user_id === userId);
        setIsAdmin(me?.role === "admin");
      })
      .catch(() => setIsAdmin(false));
  }, [token, userId]);

  useEffect(() => {
    if (!token) {
      setLoading(false);
      return;
    }
    if (!docId) {
      setLoading(false);
      setError("Invalid document ID");
      return;
    }
    setLoading(true);
    setError(null);
    fetchDocument(token, docId, { includeChunks: showChunks && isAdmin })
      .then((data) => setDoc(data))
      .catch((e) => setError(e.message ?? "Failed to load"))
      .finally(() => setLoading(false));
  }, [token, docId, showChunks, isAdmin]);

  if (auth.status === "loading" || auth.status === "unauthenticated") {
    return (
      <Card className="border-border bg-[hsl(var(--surface))]">
        <CardHeader>
          <CardTitle className="text-lg">Document</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">
            {auth.status === "loading" ? "Loading…" : "Sign in to view document."}
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      <Card className="border-border bg-[hsl(var(--surface))]">
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle className="text-lg">Document</CardTitle>
          {isAdmin && (
            <Button
              variant="secondary"
              size="sm"
              onClick={() => setShowChunks((v: boolean) => !v)}
            >
              {showChunks ? "Hide chunks" : "Show chunks"}
            </Button>
          )}
        </CardHeader>
        <CardContent>
          {loading ? (
            <p className="text-sm text-muted-foreground">Loading…</p>
          ) : error ? (
            <p className="text-sm text-destructive">{error}</p>
          ) : doc ? (
            <div className="space-y-2 text-sm">
              <div>Title: {doc.title || "Untitled"}</div>
              <div>External ID: {doc.external_id || "—"}</div>
              <div>Updated: {new Date(doc.updated_at).toLocaleString()}</div>
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">Document not found.</p>
          )}
        </CardContent>
      </Card>

      {showChunks && doc?.chunks && (
        <Card className="border-border bg-[hsl(var(--surface))]">
          <CardHeader>
            <CardTitle className="text-lg">Chunks (capped)</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {doc.chunks.slice(0, 50).map((c: RagChunk) => (
              <pre
                key={c.id}
                className="whitespace-pre-wrap rounded-[12px] border border-border bg-background p-3 text-xs text-foreground"
              >
                {c.content}
              </pre>
            ))}
          </CardContent>
        </Card>
      )}
    </div>
  );
}
