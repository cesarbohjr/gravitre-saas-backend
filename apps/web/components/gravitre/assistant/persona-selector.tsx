"use client"

import { ChevronDown, UserRound } from "lucide-react"
import { cn } from "@/lib/utils"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Button } from "@/components/ui/button"
import {
  CHAT_PERSONA_OPTIONS,
  resolveChatPersonaLabel,
  type ChatPersonaOption,
} from "@/lib/chat-personas"

type PersonaSelectorProps = {
  value: string
  onChange: (personaKey: string) => void
  disabled?: boolean
  options?: ChatPersonaOption[]
  surface?: "default" | "light"
  showIcon?: boolean
  label?: string
}

export function PersonaSelector({
  value,
  onChange,
  disabled,
  options = CHAT_PERSONA_OPTIONS,
  surface = "default",
  showIcon = true,
  label = "Response style",
}: PersonaSelectorProps) {
  const selectedLabel = resolveChatPersonaLabel(value, options)

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          type="button"
          variant="outline"
          size="sm"
          disabled={disabled}
          aria-label={`${label}: ${selectedLabel}`}
          className={cn(
            "h-8 gap-1.5 rounded-full px-3 text-xs font-medium",
            surface === "light"
              ? "border-zinc-200 bg-white text-zinc-900 hover:bg-zinc-50"
              : "border-border bg-background text-foreground",
          )}
        >
          {showIcon ? <UserRound className="h-3.5 w-3.5 opacity-70" aria-hidden /> : null}
          <span className="max-w-[9rem] truncate">{selectedLabel}</span>
          <ChevronDown className="h-3 w-3 opacity-60" aria-hidden />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-60">
        <DropdownMenuLabel className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
          {label}
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        {options.map((option) => (
          <DropdownMenuItem
            key={option.key}
            className={cn(
              "flex flex-col items-start gap-0.5 text-xs",
              value === option.key && "bg-emerald-500/10 text-emerald-700 dark:text-emerald-300",
            )}
            onClick={() => onChange(option.key)}
          >
            <span className="font-medium">{option.label}</span>
            {(option.tone || option.verbosity || option.isOrgDefault) && (
              <span className="text-[10px] text-muted-foreground">
                {[option.tone, option.verbosity].filter(Boolean).join(" · ")}
                {option.isOrgDefault ? " · org default" : ""}
              </span>
            )}
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
