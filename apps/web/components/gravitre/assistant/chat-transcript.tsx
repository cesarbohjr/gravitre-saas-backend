"use client"

import type { ReactNode } from "react"
import Link from "next/link"
import ReactMarkdown from "react-markdown"
import remarkGfm from "remark-gfm"
import { motion } from "framer-motion"
import Image from "next/image"
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
  formatMessageExactTime,
  formatMessageRelativeTime,
  messageCreatedAt,
  shouldShowClusterTimestamp,
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
 * Bare platform mark — deliberately no bubble, border or background. Gravitre is
 * the platform voice rather than another participant in the thread, so the mark
 * sits directly on the canvas (the user avatar keeps its shell).
 *
 * The box is h-9/w-9 (36px) to match `USER_AVATAR_SIZE_CLASSES.md`, the size the
 * user avatar renders at on the opposite side of the thread, so both sides of the
 * conversation carry equal visual weight and no message row shifts.
 */
function GravitreAvatarShell({
  children,
  className,
}: {
  children: ReactNode
  className?: string
}) {
  return (
    <div
      className={cn(
        "flex h-9 w-9 shrink-0 items-center justify-center text-foreground",
        className,
      )}
    >
      {children}
    </div>
  )
}

function GravitreAvatar() {
  return (
    <GravitreAvatarShell>
      {/* gravitre-mark-*.png are the icon files with their transparent padding
          cropped off (scripts/trim-icon-padding.mjs). The originals sit on a
          square canvas whose ink fills only ~49% of the width, so rendering them
          in a 36px box produced a ~16px glyph that looked far smaller than the
          36px user avatar. Cropped, `w-9` is 36px of actual mark.

          The mark is wider than it is tall, so width is the matching dimension
          and height follows the aspect ratio via object-contain.

          Without a pale shell behind it the mark also has to invert per theme.
          Both variants render and CSS picks one, so there is no
          hydration-sensitive theme read on first paint. */}
      <Image
        src="/images/gravitre-mark-black.png"
        alt="Gravitre"
        width={1053}
        height={614}
        className="w-9 object-contain dark:hidden"
      />
      <Image
        src="/images/gravitre-mark-white.png"
        alt=""
        aria-hidden
        width={1030}
        height={572}
        className="hidden w-9 object-contain dark:block"
      />
    </GravitreAvatarShell>
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
          const exactTitle = createdAt ? formatMessageExactTime(createdAt) : undefined
          const relativeLabel = createdAt ? formatMessageRelativeTime(createdAt) : null

          return (
            <motion.div
              key={message.id || `msg-${sourceIndex}`}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.18 }}
              id={`msg-${message.id}`}
              data-message-id={message.id}
              className={cn(
                "group/msg flex gap-2.5",
                isUser ? "flex-row-reverse" : "flex-row",
              )}
            >
              {isUser ? <UserAccountAvatar useCurrentUser size="md" /> : resolvedAvatar}

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
          )
        })}

        {showWaiting ? (
          <div className="flex gap-2.5">
            {assistantAvatar ? (
              resolvedAvatar
            ) : (
              <GravitreAvatarShell>
                <GravitreThinkingLoader
                  size={36}
                  className="text-foreground"
                  title={resolvedWaiting}
                />
              </GravitreAvatarShell>
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
