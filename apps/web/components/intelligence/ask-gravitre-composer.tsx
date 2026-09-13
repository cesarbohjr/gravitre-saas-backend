"use client"

/**
 * Intelligence redesign — canonical Phase 4 (2026-09-13): "Ask Gravitre"
 * composed inline UI.
 *
 * Replaces the Phase-3 `AskGravitreEntry` link-out chips with a real, inline
 * composer that talks to the SAME `/api/chat` endpoint, SAME `useChat`
 * transport shape, and SAME `data-intelligence` payload contract already
 * used by `/ai` (`AiWorkspace`) and `/agents/[id]/chat` (`AgentChatPage`) —
 * this is a second mount point of the existing, real chat path, not a
 * second chat implementation. Tool/task output is rendered through the
 * existing `ChatExecutionPanel` (the same KPI-card-mapped component the
 * full assistant workspace uses), so "closes the gap without inventing a
 * competing design system."
 *
 * Deliberately NOT wired into `GravitreAIWorkspaceProvider` /
 * `GravitreAIConversationTranscript` — those publish this conversation's
 * state into the app-wide floating-AI-helper singleton, which would make a
 * throwaway hub question appear to "take over" the global floating
 * assistant elsewhere on screen. This composer's `useChat` instance is its
 * own, self-contained, ephemeral conversation (still a real
 * `conversation_id`, still real backend history) — same pattern the org
 * chose for `/ai` vs `/agents/[id]/chat` being independent mounts.
 */

import { useCallback, useMemo, useRef, useState } from "react"
import Link from "next/link"
import useSWR from "swr"
import { useChat } from "@ai-sdk/react"
import { DefaultChatTransport } from "ai"
import { toast } from "sonner"
import { ArrowRight } from "@phosphor-icons/react"
import { ArrowUp, Loader2 } from "lucide-react"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import { TYPE } from "@/lib/design-system"
import { cn } from "@/lib/utils"
import { NucleoIntelligence } from "@/components/icons/nucleo/semantic"
import { useAuth, getAccessToken } from "@/lib/auth-context"
import { ensureSelectedOrg, buildChatOrgPayload, getSelectedOrgFromStorage } from "@/lib/org-context"
import { getEnvironmentHeader } from "@/lib/environment-context"
import { getDepartmentHeader } from "@/lib/department-context"
import { uiMessageText } from "@/lib/chat-messages"
import { parseChatError } from "@/lib/chat-errors"
import { authApi } from "@/lib/api"
import {
  ChatExecutionPanel,
  type ChatExecutionResult,
  type ChatPendingTask,
} from "@/components/gravitre/assistant/chat-execution-panel"

// Re-exported unchanged from ask-gravitre-entry.tsx — same daily-briefing
// fetch, same real-suggestions-or-labeled-fallback contract. Not
// re-implemented here so there is exactly one source of truth for it.
export { useAskGravitreSuggestions } from "@/components/intelligence/ask-gravitre-entry"

const FALLBACK_QUESTIONS = ["What changed today?", "What needs attention?", "What have you learned?"]

type IntelligenceDataPart = {
  dialogueMode?: string
  executionResult?: ChatExecutionResult
  pendingTask?: ChatPendingTask
}

export function AskGravitreComposer({
  suggestions,
  className,
  variant = "card",
}: {
  suggestions: string[] | null | undefined
  className?: string
  /** `map` — command-palette bar atop the intelligence map (no card chrome). */
  variant?: "card" | "map"
}) {
  const { user } = useAuth()
  const questions = suggestions?.length ? suggestions.slice(0, 3) : FALLBACK_QUESTIONS
  const usingFallback = !suggestions?.length

  const activeConversationIdRef = useRef<string | null>(null)
  const [conversationId, setConversationId] = useState<string | null>(null)
  const [dialogueMode, setDialogueMode] = useState<string | null>(null)
  const [executionResult, setExecutionResult] = useState<ChatExecutionResult | null>(null)
  const [pendingTask, setPendingTask] = useState<ChatPendingTask | null>(null)
  const [input, setInput] = useState("")
  const [confirming, setConfirming] = useState(false)

  // Same admin/owner approval gate as AiWorkspace's canApproveWrites — real
  // membership role for the currently selected org, not a hardcoded true.
  const { data: authMe } = useSWR(user ? "auth-me-ask-gravitre-composer" : null, () => authApi.me())
  const canApprove = (() => {
    const selectedId = getSelectedOrgFromStorage()?.id
    const orgs = (authMe as { organizations?: Array<{ id?: string; role?: string }> } | undefined)
      ?.organizations
    const matched = selectedId ? orgs?.find((org) => org.id === selectedId)?.role : undefined
    const role = (matched || (authMe as { role?: string } | undefined)?.role || "").toString().toLowerCase()
    return role === "admin" || role === "owner"
  })()

  const transport = useMemo(
    () =>
      new DefaultChatTransport({
        api: "/api/chat",
        headers: async () => {
          const token = await getAccessToken()
          const orgId = await ensureSelectedOrg()
          return {
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
            ...(orgId ? { "x-org-id": orgId } : {}),
            "x-environment": getEnvironmentHeader(),
            ...(getDepartmentHeader() ? { "x-department": getDepartmentHeader()! } : {}),
          }
        },
        body: () => ({
          ...buildChatOrgPayload(),
          mode: "fast",
          conversation_id: activeConversationIdRef.current,
          surface: "intelligence_hub",
        }),
      }),
    [],
  )

  const { messages, sendMessage, status } = useChat({
    transport,
    onError: (error) => {
      setConfirming(false)
      toast.error(parseChatError(error instanceof Error ? error : new Error(String(error))))
    },
    onFinish: () => {
      setConfirming(false)
    },
    onData: (dataPart) => {
      if (dataPart.type !== "data-intelligence" || !dataPart.data || typeof dataPart.data !== "object") {
        return
      }
      const payload = dataPart.data as IntelligenceDataPart
      if (payload.dialogueMode !== undefined) setDialogueMode(payload.dialogueMode ?? null)
      if (payload.executionResult !== undefined) setExecutionResult(payload.executionResult ?? null)
      if (payload.pendingTask !== undefined) setPendingTask(payload.pendingTask ?? null)
    },
  })

  const isBusy = status === "submitted" || status === "streaming"

  const ask = useCallback(
    (text: string) => {
      const trimmed = text.trim()
      if (!trimmed || isBusy) return
      if (!activeConversationIdRef.current) {
        activeConversationIdRef.current = crypto.randomUUID()
        setConversationId(activeConversationIdRef.current)
      }
      setDialogueMode(null)
      setExecutionResult(null)
      setPendingTask(null)
      setInput("")
      void sendMessage({ text: trimmed })
    },
    [isBusy, sendMessage],
  )

  const hasExecutionPanel = Boolean(executionResult) || Boolean(dialogueMode && pendingTask)
  const assistantUrl = conversationId ? `/ai?c=${encodeURIComponent(conversationId)}` : "/ai"

  const isMap = variant === "map"

  return (
    <section
      className={cn(
        isMap
          ? "rounded-[var(--np-radius-lg)] border border-divide/80 bg-[color:var(--g-surface-1)]/90 p-3 shadow-sm backdrop-blur-sm"
          : "rounded-[var(--np-radius-lg)] border border-divide bg-[color:var(--g-surface-1)] p-5 shadow-[var(--np-shadow)]",
        className,
      )}
      aria-labelledby="ask-gravitre-heading"
      data-ask-gravitre-composer=""
    >
      {!isMap ? (
        <div className="flex items-start gap-3">
          <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-[var(--np-radius-md)] bg-[color:var(--g-intelligence-surface)] text-[color:var(--g-intelligence)]">
            <NucleoIntelligence className="h-4 w-4" />
          </span>
          <div className="min-w-0 flex-1">
            <p className={TYPE.eyebrow}>Layer 3</p>
            <h2 id="ask-gravitre-heading" className={TYPE.sectionTitle}>
              Ask Gravitre
            </h2>
            <p className={cn(TYPE.bodyMuted, "mt-1")}>
              One question away — the same assistant that answers everywhere else in the product.
            </p>
          </div>
        </div>
      ) : (
        <p id="ask-gravitre-heading" className="sr-only">
          Ask Gravitre
        </p>
      )}

      {messages.length === 0 ? (
        <div className={cn("flex flex-wrap gap-2", isMap ? "mb-3" : "mt-4")}>
          {questions.map((question) => (
            <button
              key={question}
              type="button"
              onClick={() => ask(question)}
              className="inline-flex items-center gap-1.5 rounded-full border border-divide bg-[color:var(--g-surface-2)] px-3 py-1.5 text-xs font-medium text-[color:var(--g-text-secondary)] transition-colors hover:border-[color:var(--g-brand-border)] hover:bg-[color:var(--g-brand-surface)] hover:text-[color:var(--g-brand)]"
            >
              {question}
              <ArrowRight className="h-3 w-3" aria-hidden />
            </button>
          ))}
        </div>
      ) : (
        <div className="mt-4 max-h-96 space-y-3 overflow-y-auto pr-1" role="log" aria-live="polite">
          {messages.map((message) => {
            const text = uiMessageText(message)
            if (!text.trim() && message.role !== "assistant") return null
            return (
              <div
                key={message.id}
                className={cn(
                  "max-w-[90%] rounded-[var(--np-radius-md)] px-3 py-2 text-sm",
                  message.role === "user"
                    ? "ml-auto bg-[color:var(--g-brand-surface)] text-[color:var(--g-text-primary)]"
                    : "bg-[color:var(--g-surface-2)] text-[color:var(--g-text-primary)]",
                )}
              >
                {text.trim() || (isBusy ? "…" : "")}
              </div>
            )
          })}
          {hasExecutionPanel ? (
            <ChatExecutionPanel
              dialogueMode={dialogueMode}
              executionResult={executionResult}
              pendingTask={pendingTask}
              confirming={confirming}
              canApprove={canApprove}
              onConfirm={() => {
                setConfirming(true)
                ask("Yes, go ahead.")
              }}
              onReject={() => ask("No, cancel that.")}
              onModify={() => setInput("I'd like to change: ")}
            />
          ) : null}
        </div>
      )}

      <form
        className={cn("flex gap-2", isMap ? "" : "mt-4")}
        onSubmit={(event) => {
          event.preventDefault()
          ask(input)
        }}
      >
        <Input
          value={input}
          onChange={(event) => setInput(event.target.value)}
          placeholder={
            isMap ? "Ask Gravitre anything about your business…" : "Ask a question…"
          }
          aria-label="Ask Gravitre"
          disabled={isBusy}
          className={isMap ? "h-11 border-[color:var(--g-brand-border)]/40 bg-white/80" : undefined}
        />
        <Button type="submit" size="icon" disabled={isBusy || !input.trim()} aria-label="Send">
          {isBusy ? <Loader2 className="h-4 w-4 animate-spin" /> : <ArrowUp className="h-4 w-4" />}
        </Button>
      </form>

      {usingFallback && messages.length === 0 && !isMap ? (
        <p className={cn(TYPE.meta, "mt-3")}>
          Showing example questions — a live daily briefing wasn&apos;t available for this org yet.
        </p>
      ) : null}

      {!isMap ? (
        <div className="mt-4">
          <Link
            href={assistantUrl}
            className="inline-flex items-center gap-1 text-xs font-medium text-[color:var(--g-brand)] hover:underline"
          >
            Open the full assistant
            <ArrowRight className="h-3 w-3" aria-hidden />
          </Link>
        </div>
      ) : null}
    </section>
  )
}
