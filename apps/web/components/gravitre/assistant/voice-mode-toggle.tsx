"use client"

/**
 * Per-agent text ⇄ voice toggle for live staff use.
 *
 * Entitlement is decided server-side by the Meson `voice_interface` addon; this
 * component only renders the `voiceEntitled` result it is handed and must not
 * infer or widen access. USE seats (Lite + addon) get this toggle; CONFIGURE
 * lives in the agent voice assignment surface.
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
              // Matches the live toggle's height so swapping states never
              // reflows the composer row.
              className={cn("h-9 gap-1.5 text-muted-foreground", className)}
            >
              <Lock className="h-3.5 w-3.5" />
              Voice unavailable
            </Button>
          </TooltipTrigger>
          <TooltipContent className="max-w-xs text-xs">
            Voice requires the Meson Voice Interface addon on this organization.
          </TooltipContent>
        </Tooltip>
      </TooltipProvider>
    )
  }

  return (
    <div
      className={cn(
        "inline-flex h-9 items-center rounded-lg border border-border/70 bg-muted/40 p-0.5",
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
        // Active voice earns a quiet success tint on the mic only — enough to
        // signal a live modality without a glow stack. The label stays in the
        // normal foreground so the control still reads as a segmented toggle
        // rather than a status pill.
        className={cn("h-8 gap-1.5 px-2.5", mode === "voice" && "[&>svg]:text-success")}
        onClick={() => onChange("voice")}
        aria-pressed={mode === "voice"}
      >
        <Mic className="h-3.5 w-3.5" />
        Voice
      </Button>
    </div>
  )
}
