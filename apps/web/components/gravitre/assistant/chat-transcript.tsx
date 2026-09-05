"use client"

import { useCallback, useState, type ReactNode } from "react"
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
import { type ToolInvocation, isInternalToolGateResult } from "@/components/gravitre/assistant/tool-chip"
import { ToolExecutionGroup } from "@/components/gravitre/agent-ui/tool-execution-group"
import { ThinkingRow } from "@/components/gravitre/agent-ui/thinking-row"
import { ClarificationMessage } from "@/components/gravitre/assistant/clarification-message"
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
import { GravitreChatAvatar } from "@/components/gravitre/assistant/gravitre-chat-avatar"

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

const markdownLinkComponents = {
  a: ({ href, children, ...props }: { href?: string; children?: React.ReactNode }) => {
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
}

/**
 * The assistant avatar lives in `GravitreChatAvatar`, which implements the
 * idle / thinking / speaking states from the design handoff. It is a filled 36px
 * circle carrying the mark, so it matches the user avatar's mass on the opposite
 * side of the thread — see that component for the sizing and asset rationale.
 */

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
  onRejectExecution?: () => void
  onModifyExecution?: () => void
  canApprove?: boolean
  /** Edit a prior user message and resend as a new turn (history not overwritten). */
  onEditResend?: (messageId: string, text: string) => void
  conversationId?: string | null
  onRegenerate?: (assistantMessageId: string) => void
  onCopyText?: (text: string) => void
  onCopyLink?: (messageId: string) => void
  /** Honest no-op reporter when Save Question has no backend — parent shows toast. */
  onSaveQuestion?: (userMessageId: string, text: string) => void
  /**
   * Display name above the bubble (persona / department agent name).
   * Does not change the avatar disc — that is always the Gravitre mark.
   */
  assistantLabel?: string
  waitingLabel?: string
  isStreaming?: boolean
  agentStatusLabel?: string
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
  onRejectExecution,
  onModifyExecution,
  canApprove = false,
  onEditResend,
  conversationId,
  onRegenerate,
  onCopyText,
  onCopyLink,
  onSaveQuestion,
  // Prefer an explicit surface label; fall back to the default persona name so
  // uppercase chrome never paints a bare GRAVITRE when a caller forgets the prop.
  assistantLabel = "Friendly Assistant",
  waitingLabel,
  isStreaming = false,
  agentStatusLabel,
}: ChatTranscriptProps) {
  // Which assistant message is currently being read aloud, so that message's
  // avatar can switch to the speaking waveform. Only one can speak at a time.
  const [speakingMessageId, setSpeakingMessageId] = useState<string | null>(null)
  const handleSpeakingChange = useCallback((messageId: string, isSpeaking: boolean) => {
    setSpeakingMessageId((current) => (isSpeaking ? messageId : current === messageId ? null : current))
  }, [])

  const resolvedWaiting = agentStatusLabel ?? waitingLabel ?? `${assistantLabel} is thinking…`
  const lastAssistantId = [...messages].reverse().find((row) => row.role === "assistant")?.id
  const lastMessage = messages[messages.length - 1]
  const lastAssistantEmpty =
    lastMessage?.role === "assistant" && !uiMessageText(lastMessage).trim()
  const showAgentWorking =
    showWaiting || (isStreaming && (lastMessage?.role === "user" || lastAssistantEmpty))
  const visible = messages
    .map((message, index) => ({ message, index }))
    .filter(({ message }) => {
      const isUser = message.role === "user"
      const text = uiMessageText(message)
      const toolInvocations = !isUser
        ? extractToolInvocations(message).filter((inv) => {
            if (inv.state === "result" && isInternalToolGateResult(inv.result)) return false
            // In-flight tool calls stay in the agent bubble status — not as chips.
            if (
              isStreaming &&
              message.id === lastAssistantId &&
              inv.state === "call"
            ) {
              return false
            }
            return true
          })
        : []
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
          const isLastAssistant = message.id === lastAssistantId
          const isStreamingAssistant =
            isStreaming && isLastAssistant && message.role === "assistant"
          const toolInvocations = !isUser
            ? extractToolInvocations(message).filter((inv) => {
                if (inv.state === "result" && isInternalToolGateResult(inv.result)) return false
                if (isStreamingAssistant && inv.state === "call") return false
                return true
              })
            : []
          const displayText = isUser ? text : polishAssistantText(text)
          const showInlineStatus =
            isStreamingAssistant && !displayText.trim() && toolInvocations.length === 0
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
                <UserAccountAvatar useCurrentUser size="md" />
              ) : (
                <GravitreChatAvatar
                  state={
                    speakingMessageId === message.id
                      ? "speaking"
                      : isStreamingAssistant ||
                          toolInvocations.some((invocation) => invocation.state === "call")
                        ? "searching"
                        : showAgentWorking && isLastAssistant
                          ? "thinking"
                          : "idle"
                  }
                  title={resolvedWaiting}
                />
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
                        <ToolExecutionGroup invocations={toolInvocations} />
                      ) : null}
                      {showInlineStatus ? (
                        <ThinkingRow label={resolvedWaiting} active className="mb-2" />
                      ) : null}
                      {displayText.trim() ? (
                        dialogueMode === "clarify" && isLastAssistant ? (
                          <ClarificationMessage>
                            <ReactMarkdown
                              remarkPlugins={[remarkGfm]}
                              components={markdownLinkComponents}
                            >
                              {displayText}
                            </ReactMarkdown>
                          </ClarificationMessage>
                        ) : (
                          <ReactMarkdown
                            remarkPlugins={[remarkGfm]}
                            components={markdownLinkComponents}
                          >
                            {displayText}
                          </ReactMarkdown>
                        )
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
                            onReject={onRejectExecution}
                            onModify={onModifyExecution}
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
                    <ReadAloudButton
                      messageId={message.id}
                      text={displayText}
                      compact
                      onSpeakingChange={handleSpeakingChange}
                    />
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

        {showAgentWorking && !visible.some(({ message }) => message.id === lastMessage?.id && message.role === "assistant" && isStreaming) ? (
          <div className="flex gap-2.5">
            <GravitreChatAvatar state="thinking" title={resolvedWaiting} />
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
