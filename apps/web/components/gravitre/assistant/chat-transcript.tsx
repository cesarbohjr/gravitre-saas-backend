"use client"

import ReactMarkdown from "react-markdown"
import remarkGfm from "remark-gfm"
import { motion } from "framer-motion"
import Image from "next/image"
import { Loader2 } from "lucide-react"
import type { UIMessage } from "ai"
import { cn } from "@/lib/utils"
import { polishAssistantText } from "@/lib/plain-english"
import {
  CHAT_ASSISTANT_BUBBLE_CLASS,
  CHAT_BUBBLE_BASE_CLASS,
  CHAT_PROSE_CLASS,
  CHAT_ROLE_LABEL_CLASS,
  CHAT_USER_BUBBLE_CLASS,
  CHAT_WAITING_CLASS,
} from "@/lib/chat-typography"
import { AssistantSourceLinks } from "@/components/gravitre/assistant/assistant-source-links"
import { ExplainabilityPanel } from "@/components/gravitre/assistant/explainability-panel"
import {
  ChatExecutionPanel,
  type ChatExecutionResult,
  type ChatPendingTask,
} from "@/components/gravitre/assistant/chat-execution-panel"
import { ToolChip, type ToolInvocation } from "@/components/gravitre/assistant/tool-chip"
import { MessageActionRail } from "@/components/gravitre/assistant/message-action-rail"
import { uiMessageText } from "@/lib/chat-messages"
import { UserAccountAvatar } from "@/components/gravitre/user-account-avatar"

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
  canApprove?: boolean
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
  canApprove = false,
}: ChatTranscriptProps) {
  const lastAssistantId = [...messages].reverse().find((row) => row.role === "assistant")?.id

  return (
    <div className="mx-auto flex w-full max-w-[920px] flex-col gap-6 px-1 py-2">
      {messages.map((message) => {
        const isUser = message.role === "user"
        const text = uiMessageText(message)
        const toolInvocations = !isUser ? extractToolInvocations(message) : []
        if (isUser && !text.trim()) return null
        // Wave 6 — keep tool-only assistant bubbles so live tool chips are visible mid-stream.
        if (!isUser && !text.trim() && toolInvocations.length === 0) return null
        const displayText = isUser ? text : polishAssistantText(text)
        const isLastAssistant = message.id === lastAssistantId

        return (
          <motion.div
            key={message.id}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.22 }}
            className={cn("group flex gap-3", isUser ? "flex-row-reverse" : "flex-row")}
          >
            {isUser ? <UserAccountAvatar useCurrentUser size="lg" /> : <GravitreAvatar />}

            <div className={cn("flex min-w-0 max-w-[min(760px,88%)] flex-col", isUser ? "items-end" : "items-start")}>
              <p className={CHAT_ROLE_LABEL_CLASS}>
                {isUser ? "You" : "Gravitre AI"}
              </p>
              <div
                className={cn(
                  CHAT_BUBBLE_BASE_CLASS,
                  isUser ? CHAT_USER_BUBBLE_CLASS : CHAT_ASSISTANT_BUBBLE_CLASS,
                )}
              >
                {isUser ? (
                  <p className="whitespace-pre-wrap">{text}</p>
                ) : (
                  <div className={CHAT_PROSE_CLASS}>
                    {toolInvocations.length > 0 ? (
                      <div className="not-prose mb-2 space-y-1">
                        {toolInvocations.map((invocation) => (
                          <ToolChip key={invocation.toolCallId} invocation={invocation} />
                        ))}
                      </div>
                    ) : null}
                    {displayText.trim() ? (
                      <ReactMarkdown remarkPlugins={[remarkGfm]}>{displayText}</ReactMarkdown>
                    ) : null}
                    <AssistantSourceLinks invocations={toolInvocations} />
                    {isLastAssistant ? (
                      <>
                        <ChatExecutionPanel
                          dialogueMode={dialogueMode}
                          executionResult={executionResult}
                          pendingTask={pendingTask}
                          confirming={confirmExecuting}
                          onConfirm={onConfirmExecution}
                          canApprove={canApprove}
                        />
                        <ExplainabilityPanel
                          explanation={explainability}
                          contextExplanation={contextExplanation}
                          toolInvocations={[]}
                        />
                      </>
                    ) : null}
                  </div>
                )}
              </div>
              {!isUser && displayText.trim() ? (
                <MessageActionRail text={displayText} className="w-full max-w-full" />
              ) : null}
            </div>
          </motion.div>
        )
      })}

      {showWaiting ? (
        <div className="flex gap-3">
          <GravitreAvatar />
          <div className="flex min-w-0 max-w-[min(760px,88%)] flex-col items-start">
            <p className={CHAT_ROLE_LABEL_CLASS}>Gravitre AI</p>
            <div className={cn(CHAT_BUBBLE_BASE_CLASS, CHAT_ASSISTANT_BUBBLE_CLASS, "flex items-center gap-2", CHAT_WAITING_CLASS)}>
              <Loader2 className="h-4 w-4 animate-spin text-emerald-500" />
              Gravitre is thinking…
            </div>
          </div>
        </div>
      ) : null}
    </div>
  )
}
