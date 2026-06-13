"use client"

import { useState } from "react"
import { Loader2, Sparkles } from "lucide-react"
import { Button } from "@/components/ui/button"
import { sourcesApi } from "@/lib/api"
import type { DataSourceQueryResponse } from "@/types/api"

interface SourceQueryPanelProps {
  sourceId: string
  suggestions?: string[]
}

export function SourceQueryPanel({ sourceId, suggestions = [] }: SourceQueryPanelProps) {
  const [question, setQuestion] = useState("")
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<DataSourceQueryResponse | null>(null)

  const runQuery = async (prompt: string) => {
    const trimmed = prompt.trim()
    if (!trimmed) return
    setLoading(true)
    setError(null)
    try {
      const response = await sourcesApi.query(sourceId, trimmed)
      setResult(response)
      setQuestion(trimmed)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Query failed")
      setResult(null)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="rounded-lg border border-border bg-card p-5">
      <div className="mb-4 flex items-center justify-between">
        <div>
          <h2 className="text-sm font-semibold text-foreground">Ask your data</h2>
          <p className="text-xs text-muted-foreground mt-1">Natural language queries run as read-only SQL</p>
        </div>
        <Sparkles className="h-4 w-4 text-primary" />
      </div>

      <div className="space-y-3">
        <textarea
          value={question}
          onChange={(event) => setQuestion(event.target.value)}
          placeholder="How many customers signed up last month?"
          rows={3}
          className="w-full rounded-md border border-border bg-secondary px-3 py-2 text-sm"
        />
        <div className="flex flex-wrap gap-2">
          {suggestions.slice(0, 3).map((item) => (
            <button
              key={item}
              type="button"
              onClick={() => void runQuery(item)}
              className="rounded-full bg-secondary px-3 py-1 text-[11px] text-muted-foreground hover:text-foreground"
            >
              {item}
            </button>
          ))}
        </div>
        <Button size="sm" className="gap-2" disabled={loading || !question.trim()} onClick={() => void runQuery(question)}>
          {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
          Run query
        </Button>
      </div>

      {error ? <p className="mt-4 text-sm text-red-400">{error}</p> : null}

      {result ? (
        <div className="mt-4 space-y-3">
          <div className="rounded-md border border-border/60 bg-secondary/40 p-3">
            <p className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">Generated SQL</p>
            <pre className="mt-2 overflow-x-auto text-xs text-foreground">{result.sql}</pre>
          </div>
          {result.columns.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="border-b border-border">
                    {result.columns.map((column) => (
                      <th key={column} className="px-3 py-2 text-left text-muted-foreground">{column}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {result.rows.map((row, index) => (
                    <tr key={index} className="border-b border-border/40">
                      {result.columns.map((column) => (
                        <td key={column} className="px-3 py-2 text-foreground">
                          {String(row[column] ?? "")}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="text-xs text-muted-foreground">Query returned no rows.</p>
          )}
        </div>
      ) : null}
    </div>
  )
}
