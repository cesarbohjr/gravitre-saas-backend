"use client"

/**
 * GravitreAIFloatBridge — Phase 2 of the "Gravitre AI Agent Workspace"
 * redesign. `/ai`-specific glue between `AiWorkspace`'s real, live
 * `useChat` state and the generic `GravitreFloatingWorkspace` shell.
 *
 * See docs/delivery/ai-agent-floating-workspace-architecture-2026-09-07.md
 * Part C6 phase row 2, and the file-level comment in
 * `apps/web/components/gravitre/ai-helper.tsx` for the full rationale of why
 * Float, in this phase, is reached via `/ai` rather than a hoisted
 * cross-route `useChat` instance.
 *
 * THIS FILE OWNS NO CONVERSATION STATE OF ITS OWN — it has no `useChat`
 * call, no local message array, nothing. Every value it renders is passed
 * in as a prop by `AiWorkspace`, which is the ONE place `useChat()` is
 * called for `/ai`. That is the entire proof that Float is "the same
 * conversation, not a lookalike": there is structurally nowhere in this
 * file a second, independent conversation could come from. See
 * `apps/web/__tests__/gravitre/ai-workspace-float-bridge.test.ts` for the
 * mutation-proof test — it asserts this bridge forwards the exact same
 * `messages` array reference and the exact same `onSubmit` function
 * identity it was given, so it would fail if a future edit accidentally
 * wired Float to a second mock/instance instead of forwarding through.
 *
 * `GravitreAIConversationTranscript` / `GravitreAIConversationComposer`
 * (the Phase 1 extraction) are reused unmodified — this is a new, smaller
 * *arrangement* of them (no landing page, no research panels, no task side
 * panel, no conversation sidebar — Float is deliberately just the
 * conversation, per the architecture doc's Float-mode scope), not a fork.
 */

import type { KeyboardEvent, ReactNode, RefObject } from "react"
import { GravitreFloatingWorkspace } from "@/components/gravitre/ai-floating-workspace"
import {
  GravitreAIConversationComposer,
  GravitreAIConversationTranscript,
} from "@/components/gravitre/ai-conversation-core"
import type { UIMessage } from "ai"
import type { ChatExecutionResult, ChatPendingTask } from "@/components/gravitre/assistant/chat-execution-panel"
import type { GravitreHelperPresence } from "@/lib/gravitre-ai-presence"

export interface GravitreAIFloatBridgeProps {
  presence: GravitreHelperPresence
  onClose: () => void

  // Transcript — same values AiWorkspace's inline transcript already uses.
  messages: UIMessage[]
  showWaiting?: boolean
  isStreaming?: boolean
  status: "ready" | "submitted" | "streaming" | "error"
  isBusy?: boolean
  agentStatusLabel?: string
  dialogueMode?: string | null
  executionResult?: ChatExecutionResult | null
  pendingTask?: ChatPendingTask | null
  confirmExecuting?: boolean
  onConfirmExecution?: () => void
  onRejectExecution?: () => void
  onModifyExecution?: () => void
  canApprove?: boolean
  conversationId?: string | null
  conversationTitle?: string
  onRegenerate?: (assistantMessageId: string) => void
  assistantLabel?: string
  waitingLabel?: string

  // Composer — same values AiWorkspace's inline composer already uses.
  input: string
  onInputChange: (value: string) => void
  onSubmit: () => void
  canSubmit: boolean
  disabled?: boolean
  composerIsStreaming?: boolean
  onStop?: () => void
  voiceEntitled: boolean
  placeholder?: string
  inputRef?: RefObject<HTMLTextAreaElement | null>
  onKeyDown?: (event: KeyboardEvent<HTMLTextAreaElement>) => void

  children?: ReactNode
}

export function GravitreAIFloatBridge({
  presence,
  onClose,
  messages,
  showWaiting,
  isStreaming,
  status,
  isBusy,
  agentStatusLabel,
  dialogueMode,
  executionResult,
  pendingTask,
  confirmExecuting,
  onConfirmExecution,
  onRejectExecution,
  onModifyExecution,
  canApprove,
  conversationId,
  conversationTitle,
  onRegenerate,
  assistantLabel,
  waitingLabel,
  input,
  onInputChange,
  onSubmit,
  canSubmit,
  disabled,
  composerIsStreaming,
  onStop,
  voiceEntitled,
  placeholder,
  inputRef,
  onKeyDown,
}: GravitreAIFloatBridgeProps) {
  return (
    <GravitreFloatingWorkspace presence={presence} onClose={onClose}>
      <div className="min-h-0 flex-1 overflow-y-auto px-3 py-3">
        <GravitreAIConversationTranscript
          routeKey="/ai"
          messages={messages}
          showWaiting={showWaiting}
          isStreaming={isStreaming}
          status={status}
          isBusy={isBusy}
          agentStatusLabel={agentStatusLabel}
          dialogueMode={dialogueMode}
          executionResult={executionResult}
          pendingTask={pendingTask}
          confirmExecuting={confirmExecuting}
          onConfirmExecution={onConfirmExecution}
          onRejectExecution={onRejectExecution}
          onModifyExecution={onModifyExecution}
          canApprove={canApprove}
          conversationId={conversationId}
          conversationTitle={conversationTitle}
          onRegenerate={onRegenerate}
          assistantLabel={assistantLabel}
          waitingLabel={waitingLabel}
        />
      </div>
      <div className="shrink-0 border-t border-divide p-2.5">
        <GravitreAIConversationComposer
          input={input}
          onInputChange={onInputChange}
          onSubmit={onSubmit}
          canSubmit={canSubmit}
          showSubmit
          disabled={disabled}
          isStreaming={composerIsStreaming}
          onStop={onStop}
          voiceEntitled={voiceEntitled}
          placeholder={placeholder}
          agentLabel={assistantLabel}
          inputRef={inputRef}
          onKeyDown={onKeyDown}
          bordered={false}
        />
      </div>
    </GravitreFloatingWorkspace>
  )
}
