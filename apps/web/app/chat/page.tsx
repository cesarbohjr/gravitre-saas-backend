"use client";

import Link from "next/link";
import { useMemo, useState, type FormEvent } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/lib/use-auth";
import { getEnvironmentHeader } from "@/lib/environment";
import { retrieveRag, type RagRetrieveResponse } from "@/lib/rag-api";

export default function RagQueryPage() {
  const auth = useAuth();
  const environment = getEnvironmentHeader();
  const [query, setQuery] = useState("");
  const [topK, setTopK] = useState("8");
  const [minScore, setMinScore] = useState("");
  const [results, setResults] = useState<RagRetrieveResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const canSubmit = query.trim().length > 0 && !loading;
  const emptyMessage = useMemo(() => {
    if (loading) return "Retrieving results…";
    if (results && results.total === 0) return "No results found. Try a different query.";
    return "Ask a question to get started.";
  }, [loading, results]);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (auth.status !== "authenticated" || auth.orgId == null) return;
    const trimmedQuery = query.trim();
    if (!trimmedQuery) {
      setError("Enter a question to search.");
      return;
    }
    const parsedTopK = Number(topK);
    if (!Number.isFinite(parsedTopK) || parsedTopK < 1 || parsedTopK > 50) {
      setError("Top K must be between 1 and 50.");
      return;
    }
    const trimmedMinScore = minScore.trim();
    const parsedMinScore = trimmedMinScore ? Number(trimmedMinScore) : null;
    if (
      trimmedMinScore &&
      (!Number.isFinite(parsedMinScore) || parsedMinScore < 0 || parsedMinScore > 1)
    ) {
      setError("Min score must be between 0 and 1.");
      return;
    }
    setLoading(true);
    setError(null);
    setResults(null);
    try {
      const data = await retrieveRag(auth.token, {
        query: trimmedQuery,
        top_k: parsedTopK,
        min_score: parsedMinScore ?? undefined,
      });
      setResults(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unable to retrieve results.");
    } finally {
      setLoading(false);
    }
  };

  if (auth.status === "loading" || auth.status === "unauthenticated") {
    return (
      <Card className="border-border bg-[hsl(var(--surface))]">
        <CardHeader>
          <CardTitle className="text-lg">RAG Query</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">
            {auth.status === "loading" ? "Loading…" : "Sign in to query knowledge."}
          </p>
        </CardContent>
      </Card>
    );
  }

  if (auth.orgId == null) {
    return (
      <Card className="border-border bg-[hsl(var(--surface))]">
        <CardHeader>
          <CardTitle className="text-lg">RAG Query</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">
            Onboarding pending. Contact admin for org access to query knowledge.
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-semibold tracking-tight text-foreground">RAG Query</h1>
        <p className="text-sm text-muted-foreground">
          Environment: <span className="font-medium text-foreground">{environment}</span>
        </p>
      </div>

      <Card className="border-border bg-[hsl(var(--surface))]">
        <CardHeader>
          <CardTitle className="text-lg">Query workspace</CardTitle>
        </CardHeader>
        <CardContent>
          <form className="space-y-4" onSubmit={handleSubmit}>
            <div className="space-y-2">
              <label className="text-sm font-medium text-foreground" htmlFor="rag-query">
                Question
              </label>
              <textarea
                id="rag-query"
                rows={3}
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Ask a question about your sources…"
                className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              />
            </div>
            <div className="grid gap-4 md:grid-cols-2">
              <div className="space-y-2">
                <label className="text-sm font-medium text-foreground" htmlFor="rag-top-k">
                  Top K results
                </label>
                <input
                  id="rag-top-k"
                  type="number"
                  min={1}
                  max={50}
                  value={topK}
                  onChange={(event) => setTopK(event.target.value)}
                  className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                />
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium text-foreground" htmlFor="rag-min-score">
                  Minimum score (optional)
                </label>
                <input
                  id="rag-min-score"
                  type="number"
                  min={0}
                  max={1}
                  step={0.05}
                  value={minScore}
                  onChange={(event) => setMinScore(event.target.value)}
                  placeholder="0.5"
                  className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                />
              </div>
            </div>
            {error && <p className="text-sm text-destructive">{error}</p>}
            <div className="flex items-center gap-3">
              <Button variant="primary" size="md" type="submit" disabled={!canSubmit}>
                {loading ? "Searching…" : "Search"}
              </Button>
              <span className="text-xs text-muted-foreground">
                Results are org + environment scoped.
              </span>
            </div>
          </form>
        </CardContent>
      </Card>

      <Card className="border-border bg-[hsl(var(--surface))]">
        <CardHeader>
          <CardTitle className="text-lg">Cited results</CardTitle>
        </CardHeader>
        <CardContent>
          {loading || !results ? (
            <p className="text-sm text-muted-foreground">{emptyMessage}</p>
          ) : results.chunks.length === 0 ? (
            <p className="text-sm text-muted-foreground">{emptyMessage}</p>
          ) : (
            <div className="space-y-4">
              <div className="flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
                <span>Query ID: {results.query_id}</span>
                <span>Matches: {results.total}</span>
              </div>
              <div className="space-y-3">
                {results.chunks.map((chunk) => (
                  <div
                    key={chunk.id}
                    className="rounded-md border border-border bg-background/40 px-4 py-3"
                  >
                    <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                      <span>Score {chunk.score.toFixed(3)}</span>
                      <span>•</span>
                      <Link
                        href={`/rag/sources/${chunk.source_id}`}
                        className="text-primary hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring rounded-sm"
                      >
                        {chunk.source_title || "Source"}
                      </Link>
                      {chunk.document_id && (
                        <>
                          <span>•</span>
                          <Link
                            href={`/rag/documents/${chunk.document_id}`}
                            className="text-primary hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring rounded-sm"
                          >
                            {chunk.document_title || "Document"}
                          </Link>
                        </>
                      )}
                    </div>
                    <p className="mt-2 text-sm text-foreground">
                      {chunk.text.length > 260 ? `${chunk.text.slice(0, 260)}…` : chunk.text}
                    </p>
                    <div className="mt-2 text-xs text-muted-foreground">
                      Chunk #{chunk.chunk_index + 1}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
