"use client"

/**
 * GravitreAIWorkspaceShellBridge — Phase 3 of the "Gravitre AI Agent
 * Workspace" redesign. `/ai`-specific glue between `AiWorkspace`'s real,
 * live `useChat`/conversation-sidebar/task-panel/live-activity state and
 * the generic `GravitreAIWorkspaceShell` (Expanded/Fullscreen).
 *
 * Mirrors `ai-workspace-float-bridge.tsx`'s exact pattern and rationale —
 * see that file's header for the full explanation of why this is safe:
 * this file owns NO conversation, sidebar, or task-panel state of its own.
 * Every value it renders is a prop supplied by `AiWorkspace`, which is the
 * one place all of that state (`useChat`, `conversations` SWR list,
 * `researchProgressSteps`, `advisorBrief`, etc.) is actually computed.
 * `GravitreAILeftPanel` / `GravitreAIConversationTranscript` /
 * `GravitreAIConversationComposer` / `GravitreAIRightPanel` are reused
 * unmodified — this is a new *arrangement* of them, not a fork.
 *
 * See `__tests__/gravitre/ai-workspace-shell-bridge.test.ts` for the
 * mutation-proof test pinning down that this forwards the exact same
 * `messages` array / `onSubmit` identity Float's bridge does, and that
 * `GravitreAILeftPanel` receives the exact same `conversations` reference
 * — i.e. Expanded/Fullscreen render the SAME conversation and the SAME
 * conversation-sidebar data as Float/`/ai`, not a lookalike copy.
 */

import { useEffect, useRef, useState, type KeyboardEvent, type ReactNode, type RefObject } from "react"
import type { ChatSurfaceVoiceProps } from "@/lib/voice-duplex-controls"
import {
  GravitreAIWorkspaceShell,
  type GravitreAIWorkspaceShellMode,
} from "@/components/gravitre/ai-workspace-shell"
import { GravitreAILeftPanel, type GravitreAILeftPanelProps } from "@/components/gravitre/ai-left-panel"
import { GravitreAIRightPanel, type GravitreAIRightPanelProps } from "@/components/gravitre/ai-right-panel"
import {
  GravitreAIConversationComposer,
  GravitreAIConversationTranscript,
} from "@/components/gravitre/ai-conversation-core"
import type { UIMessage } from "ai"
import type { ChatExecutionResult, ChatPendingTask } from "@/components/gravitre/assistant/chat-execution-panel"
import type { GravitreHelperPresence } from "@/lib/gravitre-ai-presence"

export interface GravitreAIWorkspaceShellBridgeProps {
  mode: GravitreAIWorkspaceShellMode
  presence: GravitreHelperPresence
  onMinimizeToFloat: () => void
  onEnterFullscreen: () => void
  onExitFullscreen: () => void
  onClose: () => void

  // Left panel (GravitreAILeftPanel = ConversationSidebar reused as-is).
  leftPanelProps: GravitreAILeftPanelProps
  leftCollapsed: boolean
  onToggleLeft: () => void

  // Right panel (GravitreAIRightPanel = TaskSidePanel + LiveActivityRail toggle).
  rightPanelProps: Omit<GravitreAIRightPanelProps, "liveActivityOpen" | "onToggleLiveActivity">
  rightCollapsed: boolean
  onToggleRight: () => void
  liveActivityOpen: boolean
  onToggleLiveActivity: () => void

  // Center — same values AiWorkspace's inline transcript/composer already use.
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
  /** Live voice-to-voice; previously omitted, leaving this surface voice-less. */
  voice?: ChatSurfaceVoiceProps

  children?: ReactNode
}

export function GravitreAIWorkspaceShellBridge({
  mode,
  presence,
  onMinimizeToFloat,
  onEnterFullscreen,
  onExitFullscreen,
  onClose,
  leftPanelProps,
  leftCollapsed,
  onToggleLeft,
  rightPanelProps,
  rightCollapsed,
  onToggleRight,
  liveActivityOpen,
  onToggleLiveActivity,
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
  voice,
}: GravitreAIWorkspaceShellBridgeProps) {
  const bodyRef = useRef<HTMLDivElement | null>(null)
  const [orbHost, setOrbHost] = useState<HTMLDivElement | null>(null)
  useEffect(() => {
    setOrbHost(bodyRef.current)
  }, [])

  return (
    <GravitreAIWorkspaceShell
      mode={mode}
      presence={presence}
      leftCollapsed={leftCollapsed}
      onToggleLeft={onToggleLeft}
      rightCollapsed={rightCollapsed}
      onToggleRight={onToggleRight}
      onMinimizeToFloat={onMinimizeToFloat}
      onEnterFullscreen={onEnterFullscreen}
      onExitFullscreen={onExitFullscreen}
      onClose={onClose}
      leftPanel={<GravitreAILeftPanel {...leftPanelProps} />}
      rightPanel={
        <GravitreAIRightPanel
          {...rightPanelProps}
          liveActivityOpen={liveActivityOpen}
          onToggleLiveActivity={onToggleLiveActivity}
        />
      }
    >
      {/* Positioned wrapper so the contained voice orb fills the shell body rather
          than the composer strip. */}
      <div ref={bodyRef} className="relative flex min-h-0 flex-1 flex-col">
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
          activityLabel={agentStatusLabel}
          inputRef={inputRef}
          onKeyDown={onKeyDown}
          bordered={false}
          {...voice}
          voiceOrbVariant="contained"
          voiceOrbContainer={orbHost}
        />
      </div>
      </div>
    </GravitreAIWorkspaceShell>
  )
}
