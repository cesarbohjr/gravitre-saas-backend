"use client"

import type { ReactNode } from "react"
import Link from "next/link"
import ReactMarkdown from "react-markdown"
import remarkGfm from "remark-gfm"
import { motion } from "framer-motion"
import {
  BookmarkPlus,
  Copy,
  Link2,
  Pencil,
  RefreshCw,
} from "lucide-react"
import type { UIMessage } from "ai"
import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import { polishAssistantText } from "@/lib/plain-english"
import {
  CHAT_ACTION_RAIL_CLASS,
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
import { uiMessageText } from "@/lib/chat-messages"
import {
  formatMessageDayDivider,
  formatMessageExactTime,
  formatMessageRelativeTime,
  messageCreatedAt,
  shouldShowClusterTimestamp,
  shouldShowDayDivider,
} from "@/lib/chat-message-time"
import { UserAccountAvatar } from "@/components/gravitre/user-account-avatar"
import { ReadAloudButton } from "@/components/gravitre/assistant/read-aloud-button"
import { GravitreThinkingLoader } from "@/components/gravitre/assistant/thinking-loader"

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

/**
 * Shape of AI — Identifiers / Avatar: a stable brand mark so the platform
 * voice is recognizable at a glance (handoff 5a/5b ≈ glyph in brand circle).
 */
function GravitreAvatar({ className }: { className?: string }) {
  return (
    <div
      className={cn(
        "flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-[#3f5b52] text-[12px] font-bold leading-none text-white dark:bg-[#7fd8ae] dark:text-[#0a2e1f]",
        className,
      )}
      aria-hidden
    >
      ≈
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
  /** Edit a prior user message and resend as a new turn (history not overwritten). */
  onEditResend?: (messageId: string, text: string) => void
  conversationId?: string | null
  onRegenerate?: (assistantMessageId: string) => void
  onCopyText?: (text: string) => void
  onCopyLink?: (messageId: string) => void
  /** Honest no-op reporter when Save Question has no backend — parent shows toast. */
  onSaveQuestion?: (userMessageId: string, text: string) => void
  /** Override assistant identity (department / specialized agents). */
  assistantLabel?: string
  assistantAvatar?: ReactNode
  waitingLabel?: string
}

function ActionIconButton({
  label,
  onClick,
  children,
}: {
  label: string
  onClick: () => void
  children: ReactNode
}) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <button
          type="button"
          aria-label={label}
          onClick={onClick}
          className="inline-flex h-7 w-7 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
        >
          {children}
        </button>
      </TooltipTrigger>
      <TooltipContent side="bottom" className="text-xs">
        {label}
      </TooltipContent>
    </Tooltip>
  )
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
  onEditResend,
  conversationId,
  onRegenerate,
  onCopyText,
  onCopyLink,
  onSaveQuestion,
  assistantLabel = "Gravitre",
  assistantAvatar,
  waitingLabel,
}: ChatTranscriptProps) {
  const resolvedAvatar = assistantAvatar ?? <GravitreAvatar />
  const resolvedWaiting = waitingLabel ?? `${assistantLabel} is thinking…`
  const lastAssistantId = [...messages].reverse().find((row) => row.role === "assistant")?.id
  const visible = messages
    .map((message, index) => ({ message, index }))
    .filter(({ message }) => {
      const isUser = message.role === "user"
      const text = uiMessageText(message)
      const toolInvocations = !isUser ? extractToolInvocations(message) : []
      if (isUser && !text.trim()) return false
      if (!isUser && !text.trim() && toolInvocations.length === 0) return false
      return true
    })
  const visibleMessages = visible.map((row) => row.message)

  return (
    <TooltipProvider delayDuration={200}>
      <div className="mx-auto flex w-full max-w-[880px] flex-col gap-5 px-1 py-2">
        {visible.map(({ message, index: sourceIndex }, visibleIndex) => {
          const isUser = message.role === "user"
          const text = uiMessageText(message)
          const toolInvocations = !isUser ? extractToolInvocations(message) : []
          const displayText = isUser ? text : polishAssistantText(text)
          const isLastAssistant = message.id === lastAssistantId
          const createdAt = messageCreatedAt(message)
          const showRelative = shouldShowClusterTimestamp(visibleMessages, visibleIndex)
          const showDay = shouldShowDayDivider(visibleMessages, visibleIndex)
          const dayLabel = createdAt ? formatMessageDayDivider(createdAt) : null
          const exactTitle = createdAt ? formatMessageExactTime(createdAt) : undefined
          const relativeLabel = createdAt ? formatMessageRelativeTime(createdAt) : null

          return (
            <div key={message.id || `msg-${sourceIndex}`} className="contents">
            {showDay && dayLabel ? (
              <div className="flex justify-center py-1">
                <span className="rounded-full bg-[color:var(--chat-surface,#e9e7e3)] px-2.5 py-0.5 text-[10px] text-[color:var(--chat-surface-muted,#a19a91)] dark:bg-[color:var(--chat-surface,#1c1c1c)]">
                  {dayLabel}
                </span>
              </div>
            ) : null}
            <motion.div
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.18 }}
              id={`msg-${message.id}`}
              data-message-id={message.id}
              className={cn(
                "group/msg flex gap-2",
                isUser ? "flex-row-reverse" : "flex-row",
              )}
            >
              {isUser ? (
                <UserAccountAvatar
                  useCurrentUser
                  size="sm"
                  className="hidden h-6 w-6 sm:flex"
                  fallbackClassName="bg-[#3f5b52] text-[9px] text-white dark:bg-[#7fd8ae] dark:text-[#0a2e1f]"
                />
              ) : (
                resolvedAvatar
              )}

              <div
                className={cn(
                  "flex min-w-0 max-w-[min(720px,90%)] flex-col",
                  isUser ? "items-end" : "items-start",
                )}
              >
                <div
                  className={cn(
                    "flex items-baseline gap-2",
                    isUser ? "flex-row-reverse" : "flex-row",
                  )}
                >
                  <p className={CHAT_ROLE_LABEL_CLASS}>{isUser ? "You" : assistantLabel}</p>
                  {createdAt ? (
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <time
                          dateTime={createdAt}
                          title={exactTitle}
                          className={cn(
                            "cursor-default text-[11px] text-muted-foreground tabular-nums",
                            !showRelative && "sr-only",
                          )}
                        >
                          {showRelative ? relativeLabel : exactTitle}
                        </time>
                      </TooltipTrigger>
                      <TooltipContent side="top" className="text-xs font-normal tabular-nums">
                        {exactTitle}
                      </TooltipContent>
                    </Tooltip>
                  ) : null}
                </div>
                <div
                  className={cn(
                    CHAT_BUBBLE_BASE_CLASS,
                    isUser ? CHAT_USER_BUBBLE_CLASS : CHAT_ASSISTANT_BUBBLE_CLASS,
                  )}
                  title={exactTitle}
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
                        <ReactMarkdown
                          remarkPlugins={[remarkGfm]}
                          components={{
                            a: ({ href, children, ...props }) => {
                              const raw = (href || "").trim()
                              // Legacy CTAs used ?conversation=; AI page hydrates via ?c=.
                              const normalized = raw.startsWith("/ai?conversation=")
                                ? raw.replace("/ai?conversation=", "/ai?c=")
                                : raw
                              if (normalized.startsWith("/")) {
                                return (
                                  <Link href={normalized} className="underline underline-offset-2">
                                    {children}
                                  </Link>
                                )
                              }
                              if (normalized.startsWith("http://") || normalized.startsWith("https://")) {
                                return (
                                  <a
                                    href={normalized}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="underline underline-offset-2"
                                    {...props}
                                  >
                                    {children}
                                  </a>
                                )
                              }
                              return <span>{children}</span>
                            },
                          }}
                        >
                          {displayText}
                        </ReactMarkdown>
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

                <div className={cn(CHAT_ACTION_RAIL_CLASS, isUser && "flex-row-reverse")}>
                  {!isUser && displayText.trim() ? (
                    <ReadAloudButton messageId={message.id} text={displayText} compact />
                  ) : null}
                  {text.trim() && onCopyText ? (
                    <ActionIconButton label="Copy text" onClick={() => onCopyText(text)}>
                      <Copy className="h-3.5 w-3.5" />
                    </ActionIconButton>
                  ) : null}
                  {!isUser && isLastAssistant && onRegenerate ? (
                    <ActionIconButton
                      label="Regenerate"
                      onClick={() => onRegenerate(message.id)}
                    >
                      <RefreshCw className="h-3.5 w-3.5" />
                    </ActionIconButton>
                  ) : null}
                  {conversationId && onCopyLink ? (
                    <ActionIconButton
                      label="Copy link"
                      onClick={() => onCopyLink(message.id)}
                    >
                      <Link2 className="h-3.5 w-3.5" />
                    </ActionIconButton>
                  ) : null}
                  {isUser && text.trim() && onSaveQuestion ? (
                    <ActionIconButton
                      label="Save question"
                      onClick={() => onSaveQuestion(message.id, text)}
                    >
                      <BookmarkPlus className="h-3.5 w-3.5" />
                    </ActionIconButton>
                  ) : null}
                  {isUser && onEditResend && text.trim() ? (
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      className="h-7 px-2 text-[11px] text-muted-foreground"
                      onClick={() => onEditResend(message.id, text)}
                    >
                      <Pencil className="mr-1 h-3 w-3" />
                      Edit & resend
                    </Button>
                  ) : null}
                </div>
              </div>
            </motion.div>
            </div>
          )
        })}

        {showWaiting ? (
          <div className="flex gap-2">
            {assistantAvatar ? (
              resolvedAvatar
            ) : (
              <div
                className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-[#3f5b52] text-white dark:bg-[#7fd8ae] dark:text-[#0a2e1f]"
                title={resolvedWaiting}
              >
                <GravitreThinkingLoader
                  size={14}
                  className="text-current"
                  title={resolvedWaiting}
                />
              </div>
            )}
            <div className="flex min-w-0 max-w-[min(720px,90%)] flex-col items-start">
              <p className={CHAT_ROLE_LABEL_CLASS}>{assistantLabel}</p>
              <div
                className={cn(
                  CHAT_BUBBLE_BASE_CLASS,
                  CHAT_ASSISTANT_BUBBLE_CLASS,
                  "flex items-center gap-2",
                  CHAT_WAITING_CLASS,
                )}
              >
                {resolvedWaiting}
              </div>
            </div>
          </div>
        ) : null}
      </div>
    </TooltipProvider>
  )
}
