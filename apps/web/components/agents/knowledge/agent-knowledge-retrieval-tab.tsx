"use client"

import { useRef, useState } from "react"
import { Loader2, Search } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { agentKnowledgeApi } from "@/lib/api"

type RetrievalResult = Awaited<
  ReturnType<typeof agentKnowledgeApi.testRetrieval>
>
export function AgentKnowledgeRetrievalTab({ agentId }: { agentId: string }) {
  return <RetrievalWorkspace key={agentId} agentId={agentId} />
}
function RetrievalWorkspace({ agentId }: { agentId: string }) {
  const [query, setQuery] = useState("")
  const [testing, setTesting] = useState(false)
  const [result, setResult] = useState<RetrievalResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const busy = useRef(false)
  async function test() {
    const q = query.trim()
    if (!q || busy.current) return
    busy.current = true
    setTesting(true)
    setError(null)
    try {
      const response = await agentKnowledgeApi.testRetrieval(agentId, q)
      setResult({ ...response, query: q })
    } catch (err) {
      setError(err instanceof Error ? err.message : "Retrieval request failed")
    } finally {
      busy.current = false
      setTesting(false)
    }
  }
  const count =
    result &&
    typeof result.matchCount === "number" &&
    Number.isFinite(result.matchCount) &&
    result.matchCount >= 0
      ? result.matchCount
      : null
  return (
    <div className="max-w-4xl space-y-6" data-composition="understand">
      <div>
        <h2 className="font-[family-name:var(--font-space-grotesk)] text-xl font-medium">
          Check the grounding
        </h2>
        <p className="mt-2 text-sm text-muted-foreground">
          Ask a question and inspect the evidence returned for this agent. A
          retrieval result is evidence to review, rather than a measure of
          overall agent performance.
        </p>
      </div>
      <form
        className="space-y-2 border-y border-[color:var(--g-border-default)] py-5"
        onSubmit={(event) => {
          event.preventDefault()
          void test()
        }}
      >
        <label htmlFor="retrieval-test" className="text-sm font-medium">
          Question to test
        </label>
        <div className="flex flex-col gap-3 sm:flex-row">
          <Input
            id="retrieval-test"
            className="min-h-11 flex-1"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="What should this agent know?"
          />
          <Button
            type="submit"
            className="min-h-11 gap-2"
            disabled={testing || !query.trim()}
          >
            {testing ? (
              <Loader2 className="size-4 animate-spin motion-reduce:animate-none" />
            ) : (
              <Search className="size-4" />
            )}
            {testing ? "Testing…" : "Test retrieval"}
          </Button>
        </div>
      </form>
      {error && (
        <p role="alert" className="text-sm text-destructive">
          {error}. Previous returned evidence remains below.
        </p>
      )}
      {result ? (
        <section aria-label="Retrieval evidence" className="space-y-4">
          <h3 className="break-words text-sm font-medium">
            Results for “{result.query}”
          </h3>
          <dl className="flex flex-wrap gap-x-8 gap-y-3 text-sm">
            <div>
              <dt className="text-xs text-muted-foreground">
                Matches reported
              </dt>
              <dd>{count ?? "Not reported"}</dd>
            </div>
            <div>
              <dt className="text-xs text-muted-foreground">
                Assigned knowledge only
              </dt>
              <dd>
                {result.usedAssignedOnly === true
                  ? "Yes"
                  : result.usedAssignedOnly === false
                    ? "No"
                    : "Not reported"}
              </dd>
            </div>
          </dl>
          {result.missingAssignments?.length ? (
            <p className="break-words text-sm text-muted-foreground">
              Missing assignments: {result.missingAssignments.join(", ")}
            </p>
          ) : null}
          {count === 0 ? (
            <p className="text-sm text-muted-foreground">
              No matches were returned for this question. Check assigned sources
              or try a more specific question.
            </p>
          ) : null}
          <ol className="divide-y border-y border-[color:var(--g-border-default)]">
            {(result.sources ?? []).map((source, i) => (
              <li key={i} className="space-y-2 py-4">
                <h4 className="break-words text-sm font-medium">
                  {String(source.title ?? source.source ?? `Source ${i + 1}`)}
                </h4>
                <p className="text-xs text-muted-foreground">
                  Relevance:{" "}
                  {typeof source.score === "number" &&
                  Number.isFinite(source.score)
                    ? source.score.toFixed(3)
                    : "Not reported"}
                </p>
                {source.content ? (
                  <details>
                    <summary className="inline-flex min-h-11 cursor-pointer items-center text-sm underline">
                      Read returned excerpt
                    </summary>
                    <p className="whitespace-pre-wrap break-words text-sm leading-relaxed">
                      {String(source.content)}
                    </p>
                  </details>
                ) : (
                  <p className="text-xs text-muted-foreground">
                    Excerpt not reported.
                  </p>
                )}
              </li>
            ))}
          </ol>
        </section>
      ) : (
        <p className="text-sm text-muted-foreground">
          No retrieval test yet. Enter a question to inspect its returned
          evidence.
        </p>
      )}
    </div>
  )
}
