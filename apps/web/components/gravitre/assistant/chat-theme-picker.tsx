"use client"

import { Check, Palette } from "lucide-react"
import { cn } from "@/lib/utils"
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover"
import {
  CHAT_BACKGROUND_THEMES,
  type ChatBackgroundId,
} from "@/lib/chat-background-themes"

/**
 * Compact swatch picker for the chat canvas background. Lives in the /ai
 * toolbar. Purely presentational preference — selection is persisted by the
 * parent via useChatBackground(). Each swatch mirrors the real token-driven
 * pattern so the preview reads true in both light and dark.
 */
export function ChatThemePicker({
  value,
  onChange,
  className,
}: {
  value: ChatBackgroundId
  onChange: (id: ChatBackgroundId) => void
  className?: string
}) {
  const active = CHAT_BACKGROUND_THEMES.find((t) => t.id === value)

  return (
    <Popover>
      <PopoverTrigger
        className={cn(
          "inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-muted hover:text-foreground data-[state=open]:bg-muted data-[state=open]:text-foreground",
          className,
        )}
        aria-label={`Chat background: ${active?.label ?? "theme"}`}
        title="Chat background"
      >
        <Palette className="h-3.5 w-3.5" />
      </PopoverTrigger>
      <PopoverContent align="end" className="z-[70] w-72 p-3">
        <div className="mb-2 flex items-center justify-between">
          <p className="text-[13px] font-semibold text-foreground">Chat background</p>
          <span className="text-[11px] text-muted-foreground">{active?.label}</span>
        </div>
        <div className="grid grid-cols-4 gap-2">
          {CHAT_BACKGROUND_THEMES.map((theme) => {
            const isActive = theme.id === value
            return (
              <button
                key={theme.id}
                type="button"
                onClick={() => onChange(theme.id)}
                className={cn(
                  "group relative flex aspect-square items-end justify-start overflow-hidden rounded-lg border p-1.5 text-left transition-all",
                  isActive
                    ? "border-emerald-500 ring-2 ring-emerald-500/30"
                    : "border-border hover:border-emerald-500/40",
                )}
                style={{ background: theme.swatch }}
                aria-label={theme.label}
                aria-pressed={isActive}
                title={theme.description}
              >
                {isActive ? (
                  <span className="absolute right-1 top-1 flex h-4 w-4 items-center justify-center rounded-full bg-emerald-500 text-white shadow-sm">
                    <Check className="h-2.5 w-2.5" strokeWidth={3} />
                  </span>
                ) : null}
                <span className="rounded bg-background/80 px-1 text-[9px] font-medium leading-tight text-foreground backdrop-blur-sm">
                  {theme.label}
                </span>
              </button>
            )
          })}
        </div>
        <p className="mt-2.5 text-[11px] leading-snug text-muted-foreground">
          {active?.description}
        </p>
      </PopoverContent>
    </Popover>
  )
}
