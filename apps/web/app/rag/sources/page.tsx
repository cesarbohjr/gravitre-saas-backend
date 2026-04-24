"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/lib/use-auth";
import { fetchSources, type RagSource } from "@/lib/rag-api";
import { fetchOrgMembers } from "@/lib/org-api";

export default function RagSourcesPage() {
  const auth = useAuth();
  const [sources, setSources] = useState<RagSource[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isAdmin, setIsAdmin] = useState(false);
  const [adminLoading, setAdminLoading] = useState(true);

  useEffect(() => {
    if (auth.status !== "authenticated" || auth.orgId == null) {
      setAdminLoading(false);
      return;
    }
    let cancelled = false;
    setAdminLoading(true);
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
        if (!cancelled) setSources(data.sources);
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
  }, [auth.status, auth.token, auth.orgId]);

  const disabledMessage = useMemo(() => {
    if (adminLoading) return "Checking permissions…";
    if (!isAdmin) return "Admin permission required to modify sources or ingest content.";
    return "";
  }, [adminLoading, isAdmin]);

  if (auth.status === "loading" || auth.status === "unauthenticated") {
    return (
      <Card className="border-border bg-[hsl(var(--surface))]">
        <CardHeader>
          <CardTitle className="text-lg">Sources</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">
            {auth.status === "loading" ? "Loading…" : "Sign in to view sources."}
          </p>
        </CardContent>
      </Card>
    );
  }

  if (auth.orgId == null) {
    return (
      <Card className="border-border bg-[hsl(var(--surface))]">
        <CardHeader>
          <CardTitle className="text-lg">Sources</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">
            Onboarding pending. Contact admin for org access to manage sources.
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-semibold tracking-tight text-foreground">
          Sources
        </h1>
        {isAdmin ? (
          <Link href="/rag/sources/new" passHref legacyBehavior>
            <Button variant="primary" size="md" asChild>
              <a>New Source</a>
            </Button>
          </Link>
        ) : (
          <Button variant="secondary" size="md" disabled>
            New Source
          </Button>
        )}
      </div>

      {!isAdmin && (
        <Card className="border-border bg-[hsl(var(--surface))]">
          <CardContent className="pt-6">
            <p className="text-sm text-muted-foreground">{disabledMessage}</p>
          </CardContent>
        </Card>
      )}

      <Card className="border-border bg-[hsl(var(--surface))]">
        <CardHeader>
          <CardTitle className="text-lg">Registered Sources</CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <p className="text-sm text-muted-foreground">Loading…</p>
          ) : error ? (
            <p className="text-sm text-destructive">{error}</p>
          ) : sources.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              No sources yet. Create one to begin ingestion.
            </p>
          ) : (
            <table className="w-full text-left text-sm border-collapse">
              <thead>
                <tr className="border-b border-border">
                  <th className="py-2 pr-4 font-medium text-foreground">Title</th>
                  <th className="py-2 pr-4 font-medium text-foreground">Type</th>
                  <th className="py-2 pr-4 font-medium text-foreground">Documents</th>
                  <th className="py-2 font-medium text-foreground">Updated</th>
                </tr>
              </thead>
              <tbody>
                {sources.map((s) => (
                  <tr
                    key={s.id}
                    className="border-b border-border hover:bg-muted/50"
                  >
                    <td className="py-3 pr-4">
                      <Link
                        href={`/rag/sources/${s.id}`}
                        className="text-primary hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring rounded-sm"
                      >
                        {s.title}
                      </Link>
                    </td>
                    <td className="py-3 pr-4 text-muted-foreground">{s.type}</td>
                    <td className="py-3 pr-4 text-muted-foreground">—</td>
                    <td className="py-3 text-muted-foreground">
                      {new Date(s.updated_at).toLocaleString()}
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
