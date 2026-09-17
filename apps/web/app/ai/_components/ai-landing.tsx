"use client"

import { useRef } from "react"
import { motion } from "framer-motion"
import { AI_EXAMPLE_PROMPTS, type ModeId } from "./ai-mode-config"
import { SharedChatComposerControls } from "@/components/gravitre/assistant/shared-chat-composer-controls"
import type { ChatModality } from "@/components/gravitre/assistant/voice-mode-toggle"
import type { VoicePresenceState } from "@/components/gravitre/assistant/voice-session-presence"
import { toast } from "sonner"

type AiLandingProps = {
  mode: ModeId
  onModeChange: (mode: ModeId) => void
  input: string
  onInputChange: (value: string) => void
  routing: boolean
  routedTo: import("@/lib/ai-surface-handoff").AiEngine | null
  onSubmit: () => void
  onExampleSelect?: (text: string) => void
  modality: ChatModality
  onModalityChange: (next: ChatModality) => void
  voiceEntitled: boolean
  voiceUnavailableReason?: string
  duplex?: {
    active: boolean
    presence: VoicePresenceState
    levels?: number[] | null
    amplitude?: number | null
    toggle: () => void
    bargeIn: () => void
    supported?: boolean
    playbackBlocked?: boolean
    resumeBlockedPlayback?: () => void
  } | null
}

export function AiLanding({
  input,
  onInputChange,
  routing,
  onSubmit,
  onExampleSelect,
  modality,
  onModalityChange,
  voiceEntitled,
  voiceUnavailableReason,
  duplex = null,
}: AiLandingProps) {
  const inputRef = useRef<HTMLTextAreaElement>(null)
  const suggestions = AI_EXAMPLE_PROMPTS.slice(0, 4)

  const onKeyDown = (event: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key !== "Enter" || event.shiftKey) return
    if (event.nativeEvent.isComposing || event.keyCode === 229) return
    event.preventDefault()
    onSubmit()
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, ease: "easeOut" }}
      className="relative z-10 mx-auto flex w-full max-w-[720px] flex-col px-2 py-10 md:px-4 md:py-16"
      data-gravitre-ai-landing=""
    >
      <h1 className="text-balance text-center text-3xl font-semibold tracking-tight text-[color:var(--g-text-primary)] md:text-4xl">
        What do you want to get done?
      </h1>
      <p className="mx-auto mt-3 max-w-lg text-pretty text-center text-sm leading-relaxed text-[color:var(--g-text-secondary)]">
        Ask Gravitre. Answers, search, and actions stay in this conversation.
      </p>

      <div className="mt-8">
        <SharedChatComposerControls
          modality={modality}
          onModalityChange={onModalityChange}
          voiceEntitled={voiceEntitled}
          unavailableReason={voiceUnavailableReason}
          input={input}
          onInputChange={onInputChange}
          inputRef={inputRef}
          onKeyDown={onKeyDown}
          disabled={routing}
          canSubmit={Boolean(input.trim()) && !routing}
          showSubmit
          onSubmit={onSubmit}
          textareaRows={3}
          placeholder={
            modality === "voice"
              ? "Voice mode active — speak to Gravitre…"
              : "Ask, delegate, or search…"
          }
          textareaClassName="min-h-[88px] text-sm leading-relaxed"
          duplex={duplex}
          onVoiceInputError={(message) => {
            if (message) toast.error(message)
          }}
        />
      </div>

      <ul className="mt-6 flex flex-col items-center gap-2">
        {suggestions.map((prompt) => (
          <li key={prompt.text}>
            <button
              type="button"
              onClick={() =>
                onExampleSelect ? onExampleSelect(prompt.text) : onInputChange(prompt.text)
              }
              className="text-center text-sm text-[color:var(--g-text-secondary)] hover:text-[color:var(--g-text-primary)] hover:underline"
            >
              {prompt.text}
            </button>
          </li>
        ))}
      </ul>
    </motion.div>
  )
}
