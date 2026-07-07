"use client"

import ReactMarkdown from "react-markdown"
import remarkGfm from "remark-gfm"
import { motion } from "framer-motion"
import Image from "next/image"
import { Loader2 } from "lucide-react"
import { useMemo } from "react"
import type { UIMessage } from "ai"
import { cn } from "@/lib/utils"
import { polishAssistantText } from "@/lib/plain-english"
import { AssistantSourceLinks } from "@/components/gravitre/assistant/assistant-source-links"
import { ExplainabilityPanel } from "@/components/gravitre/assistant/explainability-panel"
import {
  ChatExecutionPanel,
  type ChatExecutionResult,
  type ChatPendingTask,
} from "@/components/gravitre/assistant/chat-execution-panel"
import { type ToolInvocation } from "@/components/gravitre/assistant/tool-chip"
import { uiMessageText } from "@/lib/chat-messages"
import { useAuth } from "@/lib/auth-context"
import { useUserProfile } from "@/lib/user-profile-context"

function extractToolInvocations(message: UIMessage): ToolInvocation[] {
  const invocations: ToolInvocation[] = []
  for (const part of message.parts ?? []) {
    const row = part as {
      type?: string
      toolCallId?: string
      toolName?: string
      state?: string
      output?: unknown
      result?: unknown
    }
    if (!row.type?.startsWith("tool-") && row.type !== "dynamic-tool") continue
    const toolName = row.toolName || row.type?.replace(/^tool-/, "") || "tool"
    const result = row.output ?? row.result
    const state = row.state === "output-available" || result !== undefined ? "result" : "call"
    invocations.push({
      toolCallId: row.toolCallId || `${message.id}-${toolName}-${invocations.length}`,
      toolName,
      state: state as ToolInvocation["state"],
      result,
    })
  }
  return invocations
}

function GravitreAvatar() {
  return (
    <div className="flex h-11 w-11 shrink-0 items-center justify-center overflow-hidden rounded-full bg-[#0d3b36] ring-2 ring-emerald-500/15 shadow-sm">
      <Image
        src="/images/gravitre-icon-white.png"
        alt="Gravitre"
        width={24}
        height={24}
        className="h-6 w-6 object-contain"
      />
    </div>
  )
}

function useChatUserAvatar() {
  const { user } = useAuth()
  const { profile, getInitials } = useUserProfile()

  return useMemo(() => {
    const authName =
      (user?.user_metadata?.full_name as string | undefined) ||
      (user?.user_metadata?.name as string | undefined) ||
      user?.email?.split("@")[0] ||
      "You"

    const profileSynced = Boolean(user?.email && profile.email === user.email)
    const initials = profileSynced && getInitials().trim()
      ? getInitials()
      : (() => {
          const clean = authName.trim()
          if (!clean) return "U"
          const parts = clean.split(/\s+/).filter(Boolean)
          if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase()
          return `${parts[0][0]}${parts[1][0]}`.toUpperCase()
        })()

    const image =
      (profileSynced ? profile.avatarImage : null) ||
      (user?.user_metadata?.avatar_url as string | undefined) ||
      (user?.user_metadata?.picture as string | undefined) ||
      null

    return { image, initials, name: authName }
  }, [user, profile, getInitials])
}

function ChatUserAvatar() {
  const { image, initials } = useChatUserAvatar()

  return (
    <div className="flex h-11 w-11 shrink-0 items-center justify-center overflow-hidden rounded-full bg-emerald-600 text-sm font-semibold text-white shadow-sm ring-2 ring-emerald-500/20">
      {image ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={image} alt="" className="h-full w-full object-cover" />
      ) : (
        initials
      )}
    </div>
  )
}

type ChatTranscriptProps = {
  messages: UIMessage[]
  showWaiting?: boolean
  explainability?: {
    summary?: string
    evidence?: Array<{ label?: string; kind?: string; relevance?: number }>
    confidence_note?: string
    missing_context?: string[]
  } | null
  contextExplanation?: string | null
  dialogueMode?: string | null
  executionResult?: ChatExecutionResult | null
  pendingTask?: ChatPendingTask | null
  confirmExecuting?: boolean
  onConfirmExecution?: () => void
}

export function ChatTranscript({
  messages,
  showWaiting = false,
  explainability,
  contextExplanation,
  dialogueMode,
  executionResult,
  pendingTask,
  confirmExecuting = false,
  onConfirmExecution,
}: ChatTranscriptProps) {
  const lastAssistantId = [...messages].reverse().find((row) => row.role === "assistant")?.id

  return (
    <div className="mx-auto flex w-full max-w-[920px] flex-col gap-6 px-1 py-2">
      {messages.map((message) => {
        const isUser = message.role === "user"
        const text = uiMessageText(message)
        if (isUser && !text.trim()) return null
        if (!isUser && !text.trim()) return null
        const toolInvocations = !isUser ? extractToolInvocations(message) : []
        const displayText = isUser ? text : polishAssistantText(text)

        return (
          <motion.div
            key={message.id}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.22 }}
            className={cn("flex gap-3", isUser ? "flex-row-reverse" : "flex-row")}
          >
            {isUser ? <ChatUserAvatar /> : <GravitreAvatar />}

            <div className={cn("flex min-w-0 max-w-[min(760px,88%)] flex-col", isUser ? "items-end" : "items-start")}>
              <p className="mb-1.5 px-1 text-[11px] font-medium text-muted-foreground">
                {isUser ? "You" : "Gravitre AI"}
              </p>
              <div
                className={cn(
                  "w-full rounded-[1.25rem] px-4 py-3.5 text-[15px] leading-relaxed shadow-sm",
                  isUser
                    ? "rounded-tr-md bg-emerald-600 text-white"
                    : "rounded-tl-md border border-border/60 bg-white text-foreground dark:bg-card",
                )}
              >
                {isUser ? (
                  <p className="whitespace-pre-wrap">{text}</p>
                ) : (
                  <div className="prose prose-sm max-w-none dark:prose-invert prose-p:my-2 prose-li:my-0.5 prose-headings:mb-2 prose-headings:mt-3">
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>{displayText || "…"}</ReactMarkdown>
                    <AssistantSourceLinks invocations={toolInvocations} />
                    {message.id === lastAssistantId ? (
                      <>
                        <ChatExecutionPanel
                          dialogueMode={dialogueMode}
                          executionResult={executionResult}
                          pendingTask={pendingTask}
                          confirming={confirmExecuting}
                          onConfirm={onConfirmExecution}
                        />
                        <ExplainabilityPanel
                          explanation={explainability}
                          contextExplanation={contextExplanation}
                          toolInvocations={toolInvocations}
                        />
                      </>
                    ) : null}
                  </div>
                )}
              </div>
            </div>
          </motion.div>
        )
      })}

      {showWaiting ? (
        <div className="flex gap-3">
          <GravitreAvatar />
          <div className="flex min-w-0 max-w-[min(760px,88%)] flex-col items-start">
            <p className="mb-1.5 px-1 text-[11px] font-medium text-muted-foreground">Gravitre AI</p>
            <div className="flex items-center gap-2 rounded-[1.25rem] rounded-tl-md border border-border/60 bg-white px-4 py-3.5 text-sm text-muted-foreground shadow-sm dark:bg-card">
              <Loader2 className="h-4 w-4 animate-spin text-emerald-500" />
              Gravitre is thinking…
            </div>
          </div>
        </div>
      ) : null}
    </div>
  )
}
