"use client"

/**
 * Per-agent text ⇄ voice toggle for live staff use.
 * Entitlement: currently requires Meson addon voice_interface (DECISION NEEDED
 * if plan-included access should differ — do not assume).
 */

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
  /** When false, show gated state (addon / entitlement missing). */
  voiceEntitled?: boolean
  className?: string
  disabled?: boolean
}

export function VoiceModeToggle({
  mode,
  onChange,
  voiceEntitled = true,
  className,
  disabled,
}: Props) {
  if (!voiceEntitled) {
    return (
      <TooltipProvider>
        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              type="button"
              variant="outline"
              size="sm"
              disabled
              className={cn("gap-1.5 text-muted-foreground", className)}
            >
              <Lock className="h-3.5 w-3.5" />
              Voice unavailable
            </Button>
          </TooltipTrigger>
          <TooltipContent className="max-w-xs text-xs">
            Voice requires the Meson Voice Interface addon on this org. Confirm
            whether Lite/manager seats should get a different entitlement rule.
          </TooltipContent>
        </Tooltip>
      </TooltipProvider>
    )
  }

  return (
    <div
      className={cn(
        "inline-flex items-center rounded-lg border border-border/70 bg-muted/40 p-0.5",
        className,
      )}
      role="group"
      aria-label="Chat modality"
    >
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
      <Button
        type="button"
        size="sm"
        variant={mode === "voice" ? "secondary" : "ghost"}
        disabled={disabled}
        className="h-8 gap-1.5 px-2.5"
        onClick={() => onChange("voice")}
        aria-pressed={mode === "voice"}
      >
        <Mic className="h-3.5 w-3.5" />
        Voice
      </Button>
    </div>
  )
}
