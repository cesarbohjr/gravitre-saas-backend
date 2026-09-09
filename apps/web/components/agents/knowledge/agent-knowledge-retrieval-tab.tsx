"use client"

import { useState } from "react"
import { Loader2, Search } from "lucide-react"
import { toast } from "sonner"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { agentKnowledgeApi } from "@/lib/api"

export function AgentKnowledgeRetrievalTab({ agentId }: { agentId: string }) {
  const [testQuery, setTestQuery] = useState("")
  const [testing, setTesting] = useState(false)
  const [result, setResult] = useState<{
    matchCount: number
    sources: Array<Record<string, unknown>>
    query: string
  } | null>(null)

  async function handleTest() {
    const q = testQuery.trim()
    if (!q) return
    setTesting(true)
    try {
      const res = await agentKnowledgeApi.testRetrieval(agentId, q)
      setResult({
        matchCount: res.matchCount,
        sources: res.sources ?? [],
        query: q,
      })
      toast.success(`Retrieved ${res.matchCount} assigned match${res.matchCount === 1 ? "" : "es"}`)
    } catch (error) {
      console.error("[agent-knowledge] test retrieval failed:", error)
      toast.error("Test retrieval failed")
      setResult(null)
    } finally {
      setTesting(false)
    }
  }

  return (
    <div className="space-y-6">
      <p className="text-sm text-[color:var(--g-text-muted)]">
        Test how this agent retrieves from assigned knowledge using the live retrieval pipeline — not mocked results.
      </p>

      <div className="rounded-[var(--np-radius-lg)] border border-divide bg-[color:var(--g-surface-1)] p-4">
        <label htmlFor="retrieval-test" className="text-xs font-medium text-[color:var(--g-text-muted)]">
          Test retrieval
        </label>
        <div className="mt-2 flex flex-col gap-2 sm:flex-row sm:items-end">
          <Input
            id="retrieval-test"
            value={testQuery}
            onChange={(e) => setTestQuery(e.target.value)}
            placeholder="Ask something this agent should know…"
            className="flex-1"
          />
          <Button type="button" className="gap-2" disabled={testing || !testQuery.trim()} onClick={() => void handleTest()}>
            {testing ? <Loader2 className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />}
            Test retrieval
          </Button>
        </div>
      </div>

      {result ? (
        <section className="space-y-3">
          <h2 className="text-xs font-medium uppercase tracking-wide text-[color:var(--g-text-muted)]">
            Results for &ldquo;{result.query}&rdquo;
          </h2>
          {result.matchCount === 0 ? (
            <p className="text-sm text-muted-foreground">
              No retrieval telemetry yet for this query. Assign knowledge sources or use this agent in a workflow to
              start measuring performance.
            </p>
          ) : (
            <ul className="space-y-2">
              {result.sources.map((source, i) => (
                <li
                  key={i}
                  className="rounded-md border border-divide bg-[color:var(--g-surface-2)]/50 px-3 py-2 text-sm"
                >
                  <p className="font-medium">{String(source.title ?? source.source ?? `Source ${i + 1}`)}</p>
                  {source.score != null ? (
                    <p className="text-xs tabular-nums text-[color:var(--g-text-muted)]">
                      Relevance {Number(source.score).toFixed(3)}
                    </p>
                  ) : null}
                  {source.content ? (
                    <p className="mt-1 line-clamp-3 text-xs text-[color:var(--g-text-secondary)]">
                      {String(source.content)}
                    </p>
                  ) : null}
                </li>
              ))}
            </ul>
          )}
        </section>
      ) : (
        <div className="rounded-[var(--np-radius-lg)] border border-dashed border-divide px-6 py-8 text-center text-sm text-muted-foreground">
          No retrieval telemetry yet. Test this agent or use it in a workflow to start measuring knowledge performance.
        </div>
      )}
    </div>
  )
}
