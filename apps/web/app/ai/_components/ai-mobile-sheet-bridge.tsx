"use client"

/**
 * GravitreAIMobileSheetBridge — Phase 4 of the "Gravitre AI Agent
 * Workspace" redesign. `/ai`-specific glue between `AiWorkspace`'s real,
 * live `useChat` state and the generic `GravitreAIMobileSheet` shell.
 *
 * Mirrors `ai-workspace-float-bridge.tsx`'s exact pattern and rationale —
 * see that file's header for the full explanation of why this is safe:
 * this file owns NO conversation state of its own. Every value it renders
 * is a prop supplied by `AiWorkspace`, which is the ONE place `useChat()`
 * is called for `/ai`. That is the entire proof that the mobile sheet is
 * "the same conversation, not a lookalike" — there is structurally
 * nowhere in this file a second, independent conversation could come
 * from. See `__tests__/gravitre/ai-mobile-sheet-bridge.test.ts` for the
 * mutation-proof test (same technique as
 * `ai-workspace-float-bridge.test.ts`).
 *
 * `GravitreAIConversationTranscript` / `GravitreAIConversationComposer`
 * (the Phase 1 extraction) are reused unmodified, in the exact same
 * arrangement `GravitreAIFloatBridge` already uses — mobile has no
 * left/right panel real estate, so this bridge's scope matches Float's,
 * not Expanded/Fullscreen's.
 */

import type { KeyboardEvent, ReactNode, RefObject } from "react"
import { GravitreAIMobileSheet, type GravitreAIMobileSheetMode } from "@/components/gravitre/ai-mobile-sheet"
import {
  GravitreAIConversationComposer,
  GravitreAIConversationTranscript,
} from "@/components/gravitre/ai-conversation-core"
import type { UIMessage } from "ai"
import type { ChatExecutionResult, ChatPendingTask } from "@/components/gravitre/assistant/chat-execution-panel"
import type { GravitreHelperPresence } from "@/lib/gravitre-ai-presence"

export interface GravitreAIMobileSheetBridgeProps {
  mode: GravitreAIMobileSheetMode
  presence: GravitreHelperPresence
  onModeChange: (mode: GravitreAIMobileSheetMode) => void
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

export function GravitreAIMobileSheetBridge({
  mode,
  presence,
  onModeChange,
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
}: GravitreAIMobileSheetBridgeProps) {
  return (
    <GravitreAIMobileSheet mode={mode} presence={presence} onModeChange={onModeChange} onClose={onClose}>
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
    </GravitreAIMobileSheet>
  )
}
