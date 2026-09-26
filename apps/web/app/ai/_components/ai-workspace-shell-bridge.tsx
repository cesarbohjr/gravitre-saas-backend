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
import { cn } from "@/lib/utils"
import {
  GravitreAIWorkspaceShell,
  type GravitreAIWorkspaceShellMode,
} from "@/components/gravitre/ai-workspace-shell"
import { GravitreAILeftPanel, type GravitreAILeftPanelProps } from "@/components/gravitre/ai-left-panel"
import { GravitreAIContextIndicator } from "@/components/gravitre/ai-context-indicator"
import { GravitreAIRightPanel, type GravitreAIRightPanelProps } from "@/components/gravitre/ai-right-panel"
import { GravitreAIWorkCanvas } from "@/components/gravitre/ai-work-canvas"
import { hasWorkArtifact, shouldRevealInspector } from "@/lib/gravitre-command-os"
import {
  GravitreAIConversationComposer,
  GravitreAIConversationTranscript,
} from "@/components/gravitre/ai-conversation-core"
import type { UIMessage } from "ai"
import type { ChatExecutionResult, ChatPendingTask } from "@/components/gravitre/assistant/chat-execution-panel"
import type { GravitreHelperPresence } from "@/lib/gravitre-ai-presence"
import { useOptionalGravitreAIWorkspace } from "@/components/gravitre/ai-workspace-provider"
import { GravitreAIRuntimeDetails } from "@/components/gravitre/ai-runtime-details"
import { GravitreAICompositionSwitch } from "@/components/gravitre/ai-composition-switch"
import { useCompositionPreference } from "@/hooks/use-composition-preference"
import { resolveWorkspaceComposition, writeCompositionPreference } from "@/lib/gravitre-ai-composition"
import { deriveAiRuntimeState, isApprovalPanelVisible } from "@/lib/gravitre-ai-runtime-state"
import { AiStartingState } from "./ai-starting-state"

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
  canContinueAfterStop?: boolean
  onContinueAfterStop?: () => void

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
  canContinueAfterStop,
  onContinueAfterStop,
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

  const inspectorAvailable = shouldRevealInspector({
    progressSteps: rightPanelProps.progressSteps ?? null,
    pendingTask: rightPanelProps.pendingTask ?? null,
  })
  const showWork = hasWorkArtifact({
    executionResult,
    pendingTask,
    hostedFiles: rightPanelProps.hostedFiles ?? null,
  })

  const workspace = useOptionalGravitreAIWorkspace()
  const preferredComposition = useCompositionPreference()
  const composition = resolveWorkspaceComposition({
    preferred: preferredComposition,
    hasWork: showWork,
    approvalVisible: isApprovalPanelVisible({ dialogueMode, pendingTask }),
  })
  const showTranscript = composition.composition !== "work"
  const showCanvas = composition.composition !== "conversation"
  const split = composition.composition === "split"
  const runtimeState = deriveAiRuntimeState({
    status,
    isStreaming,
    isBusy,
    dialogueMode,
    pendingTask,
    executionResult,
    confirmExecuting,
    canApprove,
    canContinueAfterStop,
  })
  const compositionSwitch = (
    <GravitreAICompositionSwitch resolved={composition} onChange={writeCompositionPreference} />
  )

  return (
    <GravitreAIWorkspaceShell
      mode={mode}
      presence={presence}
      leftCollapsed={leftCollapsed}
      onToggleLeft={onToggleLeft}
      rightCollapsed={rightCollapsed || !inspectorAvailable}
      onToggleRight={onToggleRight}
      inspectorAvailable={inspectorAvailable}
      onMinimizeToFloat={onMinimizeToFloat}
      onEnterFullscreen={onEnterFullscreen}
      onExitFullscreen={onExitFullscreen}
      onClose={onClose}
      onDock={workspace ? () => workspace.choosePresentationMode("docked") : undefined}
      titleAccessory={<GravitreAIContextIndicator className="mt-0.5" />}
      headerAccessory={compositionSwitch}
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
      <GravitreAIRuntimeDetails
        state={runtimeState}
        conversationId={conversationId}
        messages={messages}
        executionResult={executionResult}
        pendingTask={pendingTask}
      />
      <div className="flex shrink-0 justify-center border-b border-divide px-3 py-1.5 sm:hidden">{compositionSwitch}</div>
      <div
        data-gravitre-ai-composition-body={composition.composition}
        className={cn(
          "min-h-0 flex-1",
          split
            ? "grid overflow-hidden md:grid-cols-[minmax(240px,1fr)_1.15fr]"
            : showCanvas
              ? "flex flex-col overflow-hidden"
              : "overflow-y-auto px-3 py-3",
        )}
      >
        {/* Hidden, not unmounted, in Work view: scroll position and in-flight
            transcript state survive switching back. */}
        <div hidden={!showTranscript} className={cn(showCanvas && "min-h-0 overflow-y-auto px-3 py-3")}>
          {messages.length === 0 && !showWaiting && !isStreaming ? (
            <AiStartingState onInputChange={onInputChange} inputRef={inputRef} />
          ) : null}
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
            canContinueAfterStop={canContinueAfterStop}
            onContinueAfterStop={onContinueAfterStop}
          />
        </div>
        {showCanvas ? (
          <GravitreAIWorkCanvas executionResult={executionResult} pendingTask={pendingTask} />
        ) : null}
      </div>
      <div className="shrink-0 px-3 pb-3 pt-1.5">
        <div className="mx-auto w-full max-w-[760px] rounded-[8px] border border-[color:var(--g-border-strong)] bg-background p-1.5 transition-[border-color,box-shadow] focus-within:border-[color:var(--g-text-primary)] focus-within:shadow-[0_0_0_1px_var(--g-text-primary)]">
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
      </div>
    </GravitreAIWorkspaceShell>
  )
}
