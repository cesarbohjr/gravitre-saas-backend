"use client"

import Link from "next/link"
import { ArrowRight, CheckCircle2, Loader2 } from "lucide-react"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"

export type ChatExecutionResult = {
  success?: boolean
  entity_type?: string
  entity_id?: string
  url?: string
  title?: string
  body?: string
  external_url?: string | null
  task_label?: string
}

export type ChatPendingTask = {
  type?: string
  params?: Record<string, string>
}

type ChatExecutionPanelProps = {
  dialogueMode?: string | null
  executionResult?: ChatExecutionResult | null
  pendingTask?: ChatPendingTask | null
  confirming?: boolean
  onConfirm?: () => void
  className?: string
}

export function ChatExecutionPanel({
  dialogueMode,
  executionResult,
  pendingTask,
  confirming = false,
  onConfirm,
  className,
}: ChatExecutionPanelProps) {
  if (executionResult?.success && executionResult.url) {
    return (
      <div
        className={cn(
          "mt-3 rounded-xl border border-emerald-500/20 bg-emerald-500/5 px-4 py-3 text-sm",
          className,
        )}
      >
        <div className="flex items-start gap-2">
          <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-600" />
          <div className="min-w-0 flex-1">
            <p className="font-medium text-foreground">
              {executionResult.task_label || executionResult.title || "Task completed"}
            </p>
            {executionResult.body ? (
              <p className="mt-1 text-xs text-muted-foreground">{executionResult.body}</p>
            ) : null}
            <div className="mt-3 flex flex-wrap gap-2">
              <Button asChild size="sm" className="h-8">
                <Link href={executionResult.url}>
                  View in Gravitre
                  <ArrowRight className="ml-1.5 h-3.5 w-3.5" />
                </Link>
              </Button>
              {executionResult.external_url ? (
                <Button asChild size="sm" variant="outline" className="h-8">
                  <a href={executionResult.external_url} target="_blank" rel="noopener noreferrer">
                    External result
                  </a>
                </Button>
              ) : null}
            </div>
          </div>
        </div>
      </div>
    )
  }

  if (dialogueMode === "confirm" && pendingTask?.type && onConfirm) {
    return (
      <div
        className={cn(
          "mt-3 rounded-xl border border-info/20 bg-info/5 px-4 py-3 text-sm",
          className,
        )}
      >
        <p className="text-xs font-medium uppercase tracking-wide text-info">Ready to execute</p>
        <p className="mt-1 text-xs text-muted-foreground">
          {pendingTask.type === "create_agent"
            ? "Gravitre will create your agent and notify you when it is ready."
            : "Gravitre will create a draft workflow you can open in the builder."}
        </p>
        <Button
          size="sm"
          className="mt-3 h-8"
          disabled={confirming}
          onClick={onConfirm}
        >
          {confirming ? (
            <>
              <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />
              Creating…
            </>
          ) : (
            "Confirm and create"
          )}
        </Button>
      </div>
    )
  }

  return null
}
