"use client"

/**
 * GravitreAIConversation — Phase 1 extraction (state-hoisting refactor).
 *
 * See docs/delivery/ai-agent-floating-workspace-architecture-2026-09-07.md
 * Part B2: "GravitreAIConversation = today's ChatTranscript +
 * SharedChatComposerControls, made shell-agnostic."
 *
 * This file wraps the two leaf components both `/ai` (`AiWorkspace`) and
 * `/agents/[id]/chat` (`AgentChatPage`) already share (`ChatTranscript`,
 * `SharedChatComposerControls`) so that:
 *
 *  1. Both routes render through ONE shared component instead of each
 *     calling `<ChatTranscript>` / `<SharedChatComposerControls>` directly —
 *     this is the literal "extract GravitreAIConversation" ask.
 *  2. That shared component is the single place that publishes the active
 *     conversation/approval/voice state into `GravitreAIWorkspaceProvider`
 *     (via `useGravitreAIWorkspace()`), so state now flows through the
 *     shared provider rather than staying purely local to whichever page
 *     happens to be mounted.
 *
 * Deliberately NOT changed in Phase 1: the actual `useChat()` /
 * `useVoiceDuplexSession()` hook calls still live in `AiWorkspace` and
 * `AgentChatPage` respectively. Moving those into the root-mounted provider
 * would require inventing a single unified conversation-session concept that
 * works for both the org-wide `/ai` thread AND the per-agent
 * `/agents/[id]/chat` thread — that is real new architecture (Phase 2's
 * "mount + float" work, which unifies session identity across
 * presentation modes), not a zero-behavior-change refactor. Doing it here
 * would risk exactly the kind of silent behavior change this phase forbids
 * (e.g. accidentally leaking one agent's conversation into another, or into
 * the unified chat). This is flagged explicitly in the Phase 1 delivery
 * report as a resolved discrepancy against a literal reading of the
 * architecture doc's B3 ("useChat instance ... hoisted verbatim").
 *
 * Both `GravitreAIConversationTranscript` and `GravitreAIConversationComposer`
 * accept the exact same prop shapes `ChatTranscript` and
 * `SharedChatComposerControls` already accepted directly in both routes, so
 * this is a mechanical extraction — the rendered DOM is unchanged.
 */

import { useEffect } from "react"
import { ChatTranscript } from "@/components/gravitre/assistant/chat-transcript"
import {
  SharedChatComposerControls,
  type SharedChatComposerControlsProps,
} from "@/components/gravitre/assistant/shared-chat-composer-controls"
import { uiMessageText } from "@/lib/chat-messages"
import {
  useGravitreAIWorkspace,
  type GravitreAIApprovalSnapshot,
  type GravitreAIConversationSnapshot,
  type GravitreAIVoiceSnapshot,
} from "@/components/gravitre/ai-workspace-provider"
import type { UIMessage } from "ai"
import type {
  ChatExecutionResult,
  ChatPendingTask,
} from "@/components/gravitre/assistant/chat-execution-panel"
import type { VoicePresenceState } from "@/components/gravitre/assistant/voice-session-presence"
import type { ChatModality } from "@/components/gravitre/assistant/voice-mode-toggle"

export type GravitreAIConversationTranscriptProps = {
  /** "/ai" or "/agents/[id]/chat" — identifies the publisher for the shared
   * provider snapshot. Does not affect rendering. */
  routeKey: string
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
  onEditResend?: (messageId: string, text: string) => void
  conversationId?: string | null
  conversationTitle?: string
  onRegenerate?: (assistantMessageId: string) => void
  onCopyText?: (text: string) => void
  onCopyLink?: (messageId: string) => void
  onSaveQuestion?: (userMessageId: string, text: string) => void
  assistantLabel?: string
  waitingLabel?: string
  isStreaming?: boolean
  agentStatusLabel?: string
  status?: "ready" | "submitted" | "streaming" | "error"
  isBusy?: boolean
}

/**
 * Shared transcript surface. Renders `ChatTranscript` unchanged, and
 * publishes a conversation + approval snapshot into
 * `GravitreAIWorkspaceProvider` for future (Phase 2+) consumers.
 */
export function GravitreAIConversationTranscript({
  routeKey,
  messages,
  showWaiting,
  explainability,
  contextExplanation,
  dialogueMode,
  executionResult,
  pendingTask,
  confirmExecuting = false,
  onConfirmExecution,
  onRejectExecution,
  onModifyExecution,
  canApprove,
  onEditResend,
  conversationId,
  conversationTitle,
  onRegenerate,
  onCopyText,
  onCopyLink,
  onSaveQuestion,
  assistantLabel,
  waitingLabel,
  isStreaming = false,
  agentStatusLabel,
  status = "ready",
  isBusy = false,
}: GravitreAIConversationTranscriptProps) {
  const { setConversation, setApproval } = useGravitreAIWorkspace()

  useEffect(() => {
    const snapshot: GravitreAIConversationSnapshot = {
      routeKey,
      activeConversationId: conversationId ?? null,
      conversationTitle: conversationTitle ?? "",
      messages,
      status,
      isStreaming,
      isBusy,
    }
    setConversation(snapshot)
  }, [routeKey, conversationId, conversationTitle, messages, status, isStreaming, isBusy, setConversation])

  useEffect(() => {
    const snapshot: GravitreAIApprovalSnapshot = {
      dialogueMode: dialogueMode ?? null,
      pendingTask: pendingTask ?? null,
      executionResult: executionResult ?? null,
      confirmExecuting,
    }
    setApproval(snapshot)
  }, [dialogueMode, pendingTask, executionResult, confirmExecuting, setApproval])

  return (
    <ChatTranscript
      messages={messages}
      showWaiting={showWaiting}
      explainability={explainability}
      contextExplanation={contextExplanation}
      dialogueMode={dialogueMode}
      executionResult={executionResult}
      pendingTask={pendingTask}
      confirmExecuting={confirmExecuting}
      onConfirmExecution={onConfirmExecution}
      onRejectExecution={onRejectExecution}
      onModifyExecution={onModifyExecution}
      canApprove={canApprove}
      onEditResend={onEditResend}
      conversationId={conversationId}
      onRegenerate={onRegenerate}
      onCopyText={onCopyText}
      onCopyLink={onCopyLink}
      onSaveQuestion={onSaveQuestion}
      assistantLabel={assistantLabel}
      waitingLabel={waitingLabel}
      isStreaming={isStreaming}
      agentStatusLabel={agentStatusLabel}
    />
  )
}

export type GravitreAIConversationComposerProps = SharedChatComposerControlsProps & {
  /** Reflects the current text/voice modality into the shared provider —
   * does not affect rendering. */
  billingIssue?: boolean
}

/**
 * Shared composer surface. Renders `SharedChatComposerControls` unchanged,
 * and publishes a voice snapshot into `GravitreAIWorkspaceProvider`.
 */
export function GravitreAIConversationComposer(props: GravitreAIConversationComposerProps) {
  const { billingIssue, ...composerProps } = props
  const { setVoice } = useGravitreAIWorkspace()
  const { modality = "text", voicePresence = "idle", voicePresenceDetail, voiceBilling } = composerProps

  useEffect(() => {
    const snapshot: GravitreAIVoiceSnapshot = {
      modality: modality as ChatModality,
      presence: voicePresence as VoicePresenceState,
      presenceDetail: voicePresenceDetail,
      billing: Boolean(voiceBilling || billingIssue),
    }
    setVoice(snapshot)
  }, [modality, voicePresence, voicePresenceDetail, voiceBilling, billingIssue, setVoice])

  return <SharedChatComposerControls {...composerProps} />
}

/** Re-exported for callers that build snapshots directly (tests, future shells). */
export { uiMessageText }
