"use client"

/**
 * Per-agent text ⇄ voice toggle for live staff use.
 *
 * Entitlement is decided server-side (plan-included org voice + seat USE rules);
 * this component only renders the result it is handed and must not infer or
 * widen access. CONFIGURE lives in the agent voice assignment surface.
 */

import { useId } from "react"
import { Mic, MessageSquareText, Lock } from "lucide-react"
import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip"

export type ChatModality = "text" | "voice"

type Props = {
  mode: ChatModality
  onChange: (mode: ChatModality) => void
  /** When false, show gated state (org off / entitlement missing). */
  voiceEntitled?: boolean
  /** Honest reason shown when voice is unavailable. */
  unavailableReason?: string
  className?: string
  disabled?: boolean
}

export function VoiceModeToggle({
  mode,
  onChange,
  voiceEntitled = true,
  unavailableReason = "Voice is turned off for this organization, or your seat cannot use voice here. An admin can enable voice under Meson Addons / Billing.",
  className,
  disabled,
}: Props) {
  // Stable id so the gated button can point at its own explanation.
  const reasonId = useId()

  if (!voiceEntitled) {
    return (
      <TooltipProvider>
        <Tooltip>
          <TooltipTrigger asChild>
            {/*
              aria-disabled rather than the `disabled` attribute on purpose: a
              truly disabled button emits no pointer or focus events, so the
              tooltip carrying the only explanation could never open — the
              control read as inexplicably dead, especially on touch where
              there is no hover at all. This stays focusable and hoverable so
              the reason is always reachable, and onClick is not wired, so it
              still cannot start a voice session.
            */}
            <Button
              type="button"
              variant="outline"
              size="sm"
              aria-disabled
              aria-describedby={reasonId}
              className={cn(
                "h-9 cursor-not-allowed gap-1.5 text-muted-foreground opacity-60",
                className,
              )}
            >
              <Lock className="h-3.5 w-3.5" />
              Voice unavailable
            </Button>
          </TooltipTrigger>
          <TooltipContent id={reasonId} className="max-w-xs text-xs">
            {unavailableReason}
          </TooltipContent>
        </Tooltip>
      </TooltipProvider>
    )
  }

  return (
    <TooltipProvider>
      <div
        className={cn(
          "inline-flex h-9 items-center rounded-lg border border-border/70 bg-muted/40 p-0.5",
          className,
        )}
        role="group"
        aria-label="Chat modality: text or voice"
      >
        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              type="button"
              size="sm"
              variant={mode === "text" ? "secondary" : "ghost"}
              disabled={disabled}
              className="h-8 gap-1.5 px-2.5"
              onClick={() => onChange("text")}
              aria-pressed={mode === "text"}
            >
              <MessageSquareText className="h-3.5 w-3.5" />
              Text
            </Button>
          </TooltipTrigger>
          <TooltipContent className="text-xs">Type replies in this conversation</TooltipContent>
        </Tooltip>
        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              type="button"
              size="sm"
              variant={mode === "voice" ? "secondary" : "ghost"}
              disabled={disabled}
              className={cn("h-8 gap-1.5 px-2.5", mode === "voice" && "[&>svg]:text-success")}
              onClick={() => onChange("voice")}
              aria-pressed={mode === "voice"}
            >
              <Mic className="h-3.5 w-3.5" />
              Voice
            </Button>
          </TooltipTrigger>
          <TooltipContent className="max-w-xs text-xs">
            Speak with the agent — live STT + TTS in this same conversation
          </TooltipContent>
        </Tooltip>
      </div>
    </TooltipProvider>
  )
}
